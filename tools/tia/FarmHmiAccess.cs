using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.CompilerServices;
using Siemens.Engineering;
using Siemens.Engineering.Compiler;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.HmiUnified;
using Siemens.Engineering.HmiUnified.UI.Base;
using Siemens.Engineering.Umac;

// Configure the existing FarmHMI controls in an explicitly selected, open TIA V19 project.
// No users or credentials are created. No project is downloaded by this tool.
internal static class FarmHmiAccess
{
    private const string AdminRightName = "Farm administration";
    private const string AdminRoleName = "Farm HMI administrator";
    private const string HmiAdminName = "HMI Administrator";
    private const string HmiOperatorName = "HMI Operator";
    private const string OperateRightName = "Operate";

    private static readonly string[] OperatorControls = { "Z_Dur", "Z_Start", "Z_Stop", "Z_StopAll" };
    private static readonly string[] ModeControls = { "St_M0", "St_M1", "St_M2", "St_M3" };

    private static int Main(string[] args)
    {
        if (args.Length != 2 || (args[0] != "inspect" && args[0] != "apply"))
        {
            Console.Error.WriteLine("Usage: FarmHmiAccess.exe inspect|apply <open project.ap19>");
            return 2;
        }

        string apiDir = Environment.GetEnvironmentVariable("FARM_TIA_V19_API");
        if (String.IsNullOrWhiteSpace(apiDir))
        {
            Console.Error.WriteLine("Set FARM_TIA_V19_API to the TIA Portal PublicAPI/V19 folder.");
            return 2;
        }

        AppDomain.CurrentDomain.AssemblyResolve += (sender, request) =>
        {
            string dll = Path.Combine(apiDir, new AssemblyName(request.Name).Name + ".dll");
            return File.Exists(dll) ? Assembly.LoadFrom(dll) : null;
        };

        try
        {
            return Configure(args[0] == "apply", Path.GetFullPath(args[1]));
        }
        catch (Exception error)
        {
            Console.Error.WriteLine(error.GetType().Name + ": " + error.Message);
            return 1;
        }
    }

    [MethodImpl(MethodImplOptions.NoInlining)]
    private static int Configure(bool apply, string path)
    {
        var process = TiaPortal.GetProcesses().SingleOrDefault(p => p.ProjectPath != null &&
            String.Equals(p.ProjectPath.FullName, path, StringComparison.OrdinalIgnoreCase));
        if (process == null)
            throw new InvalidOperationException("The specified project is not open in TIA Portal.");

        using (var portal = process.Attach())
        {
            var project = portal.Projects.SingleOrDefault(p =>
                String.Equals(p.Path.FullName, path, StringComparison.OrdinalIgnoreCase));
            if (project == null)
                throw new InvalidOperationException("The selected TIA session does not own the specified project.");
            var station = project.Devices.SingleOrDefault(d => d.Name == "FarmHMI");
            if (station == null)
                throw new InvalidOperationException("FarmHMI is missing from the selected project.");
            var item = Children(station.DeviceItems).SingleOrDefault(i =>
            {
                var software = i.GetService<SoftwareContainer>();
                return software != null && software.Software is HmiSoftware;
            });
            if (item == null)
                throw new InvalidOperationException("FarmHMI has no Unified HMI software.");
            var hmi = (HmiSoftware)item.GetService<SoftwareContainer>().Software;
            var umac = project.GetService<UmacConfigurator>();
            // The station owns the HMI rights. Its software item can expose a
            // UmacDevice service even when that service has no assignable rights.
            var device = station.GetService<UmacDevice>();
            if (umac == null || device == null)
                throw new InvalidOperationException("Native project or device user management is unavailable.");

            var activeNamedUsers = umac.ProjectUsers.Where(user => user.IsActive &&
                !String.Equals(user.Name, "Anonymous", StringComparison.OrdinalIgnoreCase)).ToList();
            var enteredAdmins = activeNamedUsers.Where(user =>
                user.Roles.Any(role => role.Name == HmiAdminName)).ToList();
            var operatorCount = activeNamedUsers.Count(user =>
                user.Roles.Any(role => role.Name == HmiOperatorName) &&
                !user.Roles.Any(role => role.Name == HmiAdminName || role.Name == AdminRoleName));
            Console.WriteLine("Existing named HMI administrators: " + enteredAdmins.Count);
            Console.WriteLine("Existing named HMI operators without administrator roles: " + operatorCount);
            Console.WriteLine("FarmHMI device function rights: " + device.AvailableDeviceFunctionRights.Count);
            var operate = device.AvailableDeviceFunctionRights.SingleOrDefault(r => r.Name == OperateRightName);
            if (operate == null)
            {
                var names = device.AvailableDeviceFunctionRights.Select(r => r.Name);
                throw new InvalidOperationException("The HMI Operate right is missing. Check FarmHMI Runtime settings and the project Users and roles. Available rights: " +
                    String.Join(", ", names));
            }
            var operatorItems = FindItems(hmi, "Zone", OperatorControls).ToList();
            var adminItems = FindItems(hmi, "Settings", ModeControls)
                .Concat(FindItems(hmi, "Alarms", new[] { "A_Reset" })).ToList();

            if (apply)
            {
                if (enteredAdmins.Count == 0)
                    throw new InvalidOperationException("Assign the HMI Administrator role to an active named project user before applying these rights.");

                using (var access = portal.ExclusiveAccess("Configure FarmHMI control rights"))
                {
                    using (var transaction = access.Transaction(project, "FarmHMI control rights"))
                    {
                        var adminRight = umac.CustomDeviceFunctionRights.FirstOrDefault(r => r.Name == AdminRightName)
                            ?? umac.CustomDeviceFunctionRights.Create(
                                AdminRightName, "Farm-PLC", "Change system mode and reset alarms");
                        var adminRole = umac.CustomRoles.FirstOrDefault(r => r.Name == AdminRoleName)
                            ?? umac.CustomRoles.Create(AdminRoleName, "Administrator controls on FarmHMI");
                        if (!adminRole.GetAssignedDeviceFunctionRights(device).Any(r => r.Identifier == adminRight.Identifier))
                            adminRole.AssignDeviceFunctionRight(device, adminRight);
                        foreach (var user in enteredAdmins)
                        {
                            if (!user.Roles.Any(role => role.Identifier == adminRole.Identifier))
                                user.Roles.Add(adminRole);
                        }
                        foreach (var control in operatorItems)
                            control.Authorization = operate.Name;
                        foreach (var control in adminItems)
                            control.Authorization = adminRight.Name;
                        transaction.CommitOnDispose();
                    }
                }
                var compile = item.GetService<ICompilable>().Compile();
                Console.WriteLine("FarmHMI compile: " + compile.ErrorCount + " errors, " +
                                  compile.WarningCount + " warnings");
                if (compile.ErrorCount != 0)
                {
                    PrintCompilerErrors(compile.Messages);
                    return 1;
                }
                project.Save();
            }

            foreach (var control in operatorItems.Concat(adminItems))
                Console.WriteLine(control.Name + ": " + (control.Authorization ?? "(unrestricted)"));
            return 0;
        }
    }

    private static IEnumerable<DeviceItem> Children(IEnumerable<DeviceItem> items)
    {
        foreach (var item in items)
        {
            yield return item;
            foreach (var child in Children(item.DeviceItems))
                yield return child;
        }
    }

    private static IEnumerable<HmiSimpleScreenItemBase> FindItems(
        HmiSoftware hmi, string screenName, IEnumerable<string> names)
    {
        var screen = hmi.Screens.Find(screenName);
        if (screen == null)
            throw new InvalidOperationException("Missing screen " + screenName);
        foreach (string name in names)
        {
            var item = screen.ScreenItems.Find(name) as HmiSimpleScreenItemBase;
            if (item == null)
                throw new InvalidOperationException("Missing operable item " + screenName + "." + name);
            yield return item;
        }
    }

    private static void PrintCompilerErrors(CompilerResultMessageComposition messages)
    {
        foreach (var message in messages)
        {
            if (message.State == CompilerResultState.Error)
                Console.Error.WriteLine(message.Path + ": " + message.Description);
            PrintCompilerErrors(message.Messages);
        }
    }
}
