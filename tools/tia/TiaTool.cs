// TiaTool - one stable binary for TIA Portal Openness work.
// Farm-PLC copy (G5): adds --device, plug, project-dump and project-set.
//
// Deliberately a single exe with subcommands rather than a family of small tools:
// TIA whitelists an Openness client by executable path + FILE HASH, so every rebuild
// triggers a fresh "Allow access?" prompt. One binary, approved once, rebuilt rarely,
// keeps that dialog out of the way without weakening the consent gate.
//
// Build:  scripts/build.sh          (or see the csc line inside it)
// Usage:  TiaTool.exe <subcommand> [args...]
//         TiaTool.exe help
//
// Adjust PortalDir and DefaultProject for the installation at hand.

using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Threading;
using Siemens.Engineering;
using Siemens.Engineering.HW;
using Siemens.Engineering.HW.Features;
using Siemens.Engineering.SW;
using Siemens.Engineering.SW.Blocks;

static class Cfg
{
    // The install is not always on C: - this machine's was on F: - so find it rather than
    // assume. Override with the TIA_PORTAL_DIR environment variable when autodetection
    // guesses wrong or several versions are installed.
    public const string Version = "V19";
    public static string DefaultProject = Environment.GetEnvironmentVariable("TIA_PROJECT") ?? "";
    public static string DeviceName = "";

    public static readonly string PortalDir = FindPortal();
    public static string[] SearchDirs = PortalDir == null ? new string[0] : new[] {
        Path.Combine(PortalDir, @"PublicAPI\" + Version),
        // Siemens.Engineering.Contract.dll lives here, NOT in PublicAPI\<ver>.
        Path.Combine(PortalDir, @"Bin\PublicAPI"),
        Path.Combine(PortalDir, "Bin"),
    };

    static string FindPortal()
    {
        string env = Environment.GetEnvironmentVariable("TIA_PORTAL_DIR");
        if (!string.IsNullOrEmpty(env) && Probe(env)) return env;

        foreach (string drive in new[] { "C", "D", "E", "F", "G" })
            foreach (string pf in new[] { "Program Files", "Program Files (x86)" })
            {
                string dir = drive + @":\" + pf + @"\Siemens\Automation\Portal " + Version;
                if (Probe(dir)) return dir;
            }
        return null;
    }

    static bool Probe(string dir)
    {
        return File.Exists(Path.Combine(dir, @"PublicAPI\" + Version + @"\Siemens.Engineering.dll"));
    }
}

static class Program
{
    static Assembly Resolve(object sender, ResolveEventArgs args)
    {
        // Guarded: mixed-mode requests can carry names with characters Path.Combine
        // rejects, which surfaces as a baffling "Illegal characters in path".
        try
        {
            string name = new AssemblyName(args.Name).Name;
            if (string.IsNullOrEmpty(name)) return null;
            if (name.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0) return null;
            foreach (string dir in Cfg.SearchDirs)
            {
                string dll = Path.Combine(dir, name + ".dll");
                if (File.Exists(dll)) return Assembly.LoadFrom(dll);
            }
            return null;
        }
        catch { return null; }
    }

    static int Main(string[] argv)
    {
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;

        // Handled here, before Run: entering Run makes the JIT resolve the Siemens types
        // in its body, so `help` would otherwise fail on a machine where the portal
        // directory was not found.
        if (argv.Length == 0 || argv[0] == "help" || argv[0] == "--help")
        {
            Usage();
            Console.WriteLine();
            Console.WriteLine(Cfg.PortalDir == null
                ? "TIA Portal " + Cfg.Version + " NOT FOUND - set TIA_PORTAL_DIR to its folder."
                : "TIA Portal: " + Cfg.PortalDir);
            return 0;
        }

        if (Cfg.PortalDir == null)
        {
            Console.WriteLine("ERROR: could not find TIA Portal " + Cfg.Version + ".");
            Console.WriteLine("Set TIA_PORTAL_DIR to the folder containing PublicAPI\\" + Cfg.Version + ".");
            return 2;
        }

        return Run(argv);
    }

    // Kept separate so the JIT does not resolve Siemens types before the handler is wired up.
    [System.Runtime.CompilerServices.MethodImpl(
        System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    static int Run(string[] argv)
    {
        if (argv.Length == 0 || argv[0] == "help" || argv[0] == "--help")
        {
            Usage();
            return 0;
        }

        string cmd = argv[0];
        string[] rest = argv.Skip(1).ToArray();
        string projectPath = TakeOption(ref rest, "--project", Cfg.DefaultProject);
        Cfg.DeviceName = TakeOption(ref rest, "--device", "");

        TiaPortal portal = null;
        try
        {
            portal = AttachWithRetry();
            Project project = OpenOrAttachProject(portal, projectPath);
            Console.WriteLine("project: " + project.Name);

            switch (cmd)
            {
                case "devices":    return CmdDevices(project);
                case "dump":       return CmdDump(project, rest);
                case "set":        return CmdSet(project, rest);
                case "block-dump": return CmdBlockDump(project, rest);
                case "block-set":  return CmdBlockSet(project, rest);
                case "add-device": return CmdAddDevice(project, rest);
                case "plug":       return CmdPlug(project, rest);
                case "project-dump": DumpAttributes((IEngineeringObject)project, rest.Length > 0 ? rest[0] : null, "  . "); return 0;
                case "project-set":  return CmdProjectSet(project, rest);
                default:
                    Console.WriteLine("unknown subcommand: " + cmd);
                    Usage();
                    return 1;
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine("ERROR " + ex.GetType().Name + ": " + ex.Message);
            return 2;
        }
        finally
        {
            if (portal != null) portal.Dispose();
        }
    }

    static void Usage()
    {
        Console.WriteLine(@"TiaTool [--project <path.ap19>] <subcommand>

  devices                                   list devices and device items
  dump      <item> [filter]                 attributes of a device item
                                            <item> = cpu | opcua | <name> | slot:<n>
  set       <item> <Attr> <val> [...]       set attributes (several pairs per run)
  block-dump <Block> [filter]               attributes of a block (CyclicTime, MemoryLayout...)
  block-set  <Block> <Attr> <val>           set one block attribute
  add-device <OrderNumber> <Name> [fw...]   create a station, trying each firmware in turn
  plug <slot> <OrderNumber> <Name> [fw...]  plug a module into the device's rack (try each fw; - = none)
  project-dump [filter]                     project attributes
  project-set <Attr> <val>                  set a project attribute (e.g. simulation support)
  --device <name>                           pick the device (default: the first one)

Attribute values are typed from the attribute's current value, so pass them bare:
  TiaTool set opcua OpcUaUmacUserConfiguration false OpcUaServerCertificateSettings 0");
    }

    // ---------- plumbing ----------

    static string TakeOption(ref string[] args, string name, string fallback)
    {
        var list = args.ToList();
        int i = list.IndexOf(name);
        if (i < 0 || i + 1 >= list.Count) return fallback;
        string value = list[i + 1];
        list.RemoveRange(i, 2);
        args = list.ToArray();
        return value;
    }

    // Attach intermittently throws EngineeringSecurityException / times out and then
    // works on a retry. Retrying here beats making every caller handle it.
    static TiaPortal AttachWithRetry(int attempts = 3)
    {
        Exception last = null;
        for (int i = 1; i <= attempts; i++)
        {
            try
            {
                var procs = TiaPortal.GetProcesses();
                if (procs.Count == 0) throw new InvalidOperationException("no TIA Portal running");
                return procs[0].Attach();
            }
            catch (Exception ex)
            {
                last = ex;
                Console.WriteLine("attach attempt " + i + " failed: " + ex.Message);
                if (i < attempts) Thread.Sleep(3000);
            }
        }
        throw last;
    }

    // An MCP server's disconnect may have closed the project, so reopen it when needed.
    static Project OpenOrAttachProject(TiaPortal portal, string projectPath)
    {
        if (portal.Projects.Count > 0)
        {
            if (string.IsNullOrEmpty(projectPath)) return portal.Projects[0];
            string want = Path.GetFileNameWithoutExtension(projectPath);
            var hit = portal.Projects.FirstOrDefault(p => p.Name == want);
            if (hit != null) return hit;
        }
        if (string.IsNullOrEmpty(projectPath))
            throw new InvalidOperationException("no project open and no --project given");
        Console.WriteLine("opening " + projectPath);
        return portal.Projects.Open(new FileInfo(projectPath));
    }

    static Device FirstDevice(Project project)
    {
        var dev = string.IsNullOrEmpty(Cfg.DeviceName)
            ? project.Devices.FirstOrDefault()
            : project.Devices.FirstOrDefault(d => d.Name == Cfg.DeviceName);
        if (dev == null) throw new InvalidOperationException("project has no devices");
        return dev;
    }

    static DeviceItem ResolveItem(Device dev, string spec)
    {
        if (spec == "cpu") return Search(dev, i => i.Classification.ToString() == "CPU");
        if (spec == "opcua")
            return Search(dev, i => i.PositionNumber == 254 || i.Name.StartsWith("OPC UA"));
        if (spec.StartsWith("slot:"))
        {
            int n = int.Parse(spec.Substring(5));
            return Search(dev, i => i.PositionNumber == n);
        }
        return Search(dev, i => i.Name == spec);
    }

    static DeviceItem Search(Device dev, Func<DeviceItem, bool> pred)
    {
        foreach (var top in dev.DeviceItems)
        {
            var hit = SearchItem(top, pred);
            if (hit != null) return hit;
        }
        return null;
    }

    static DeviceItem SearchItem(DeviceItem item, Func<DeviceItem, bool> pred)
    {
        if (pred(item)) return item;
        foreach (var c in item.DeviceItems)
        {
            var hit = SearchItem(c, pred);
            if (hit != null) return hit;
        }
        return null;
    }

    static PlcBlock FindBlock(PlcBlockGroup grp, string name)
    {
        var hit = grp.Blocks.FirstOrDefault(b => b.Name == name);
        if (hit != null) return hit;
        foreach (var g in grp.Groups)
        {
            var r = FindBlock(g, name);
            if (r != null) return r;
        }
        return null;
    }

    static PlcSoftware FindSoftware(Project project)
    {
        foreach (Device d in project.Devices)
            foreach (DeviceItem di in d.DeviceItems)
            {
                var p1 = di.GetService<SoftwareContainer>();
                if (p1 != null && p1.Software is PlcSoftware) return (PlcSoftware)p1.Software;
                foreach (DeviceItem sub in di.DeviceItems)
                {
                    var p2 = sub.GetService<SoftwareContainer>();
                    if (p2 != null && p2.Software is PlcSoftware) return (PlcSoftware)p2.Software;
                }
            }
        return null;
    }

    // Openness refuses a type mismatch outright, so convert from what the attribute holds.
    static object Coerce(object current, string value)
    {
        if (current is bool)   return bool.Parse(value);
        if (current is int)    return int.Parse(value);
        if (current is uint)   return uint.Parse(value);
        if (current is short)  return short.Parse(value);
        if (current is ushort) return ushort.Parse(value);
        if (current is byte)   return byte.Parse(value);
        if (current is long)   return long.Parse(value);
        if (current is ulong)  return ulong.Parse(value);
        if (current is double) return double.Parse(value);
        if (current is float)  return float.Parse(value);
        if (current != null && current.GetType().IsEnum)
            return Enum.Parse(current.GetType(), value, true);
        return value;
    }

    static void DumpAttributes(IEngineeringObject eo, string filter, string indent)
    {
        foreach (var ai in eo.GetAttributeInfos())
        {
            if (filter != null && ai.Name.IndexOf(filter, StringComparison.OrdinalIgnoreCase) < 0)
                continue;
            object v;
            try { v = eo.GetAttribute(ai.Name); }
            catch (Exception ex) { v = "<" + ex.GetType().Name + ">"; }
            Console.WriteLine(indent + ai.Name + " = " + v);
        }
    }

    static void SetAttribute(IEngineeringObject eo, string attr, string value)
    {
        object cur = eo.GetAttribute(attr);
        Console.WriteLine("  " + attr + ": " + cur
            + " (" + (cur == null ? "null" : cur.GetType().Name) + ")");
        eo.SetAttribute(attr, Coerce(cur, value));
        Console.WriteLine("    -> " + eo.GetAttribute(attr));
    }

    // ---------- subcommands ----------

    static int CmdDevices(Project project)
    {
        foreach (Device d in project.Devices)
        {
            Console.WriteLine(d.Name + "   type=" + d.TypeIdentifier);
            foreach (var i in d.DeviceItems) PrintItem(i, "  ");
        }
        return 0;
    }

    static void PrintItem(DeviceItem item, string indent)
    {
        Console.WriteLine(indent + "[" + item.PositionNumber + "] " + item.Name
                          + "  (" + item.Classification + ")");
        foreach (var c in item.DeviceItems) PrintItem(c, indent + "  ");
    }

    static int CmdDump(Project project, string[] a)
    {
        if (a.Length < 1) { Console.WriteLine("usage: dump <item> [filter]"); return 1; }
        var item = ResolveItem(FirstDevice(project), a[0]);
        if (item == null) { Console.WriteLine("item not found: " + a[0]); return 3; }
        Console.WriteLine("item: " + item.Name + " (slot " + item.PositionNumber + ")");
        DumpAttributes((IEngineeringObject)item, a.Length > 1 ? a[1] : null, "  . ");
        return 0;
    }

    static int CmdSet(Project project, string[] a)
    {
        if (a.Length < 3 || a.Length % 2 == 0)
        {
            Console.WriteLine("usage: set <item> <Attr> <value> [<Attr> <value> ...]");
            return 1;
        }
        var item = ResolveItem(FirstDevice(project), a[0]);
        if (item == null) { Console.WriteLine("item not found: " + a[0]); return 3; }
        Console.WriteLine("item: " + item.Name + " (slot " + item.PositionNumber + ")");
        for (int i = 1; i + 1 < a.Length; i += 2)
            SetAttribute((IEngineeringObject)item, a[i], a[i + 1]);
        project.Save();
        Console.WriteLine("saved");
        return 0;
    }

    static int CmdBlockDump(Project project, string[] a)
    {
        if (a.Length < 1) { Console.WriteLine("usage: block-dump <Block> [filter]"); return 1; }
        var sw = FindSoftware(project);
        var blk = FindBlock(sw.BlockGroup, a[0]);
        if (blk == null) { Console.WriteLine("block not found: " + a[0]); return 3; }
        Console.WriteLine("block: " + blk.Name + " (" + blk.GetType().Name + ", No " + blk.Number + ")");
        DumpAttributes((IEngineeringObject)blk, a.Length > 1 ? a[1] : null, "  . ");
        return 0;
    }

    static int CmdBlockSet(Project project, string[] a)
    {
        if (a.Length < 3) { Console.WriteLine("usage: block-set <Block> <Attr> <value>"); return 1; }
        var sw = FindSoftware(project);
        var blk = FindBlock(sw.BlockGroup, a[0]);
        if (blk == null) { Console.WriteLine("block not found: " + a[0]); return 3; }
        Console.WriteLine("block: " + blk.Name);
        SetAttribute((IEngineeringObject)blk, a[1], a[2]);
        project.Save();
        Console.WriteLine("saved");
        return 0;
    }

    static int CmdAddDevice(Project project, string[] a)
    {
        if (a.Length < 2)
        {
            Console.WriteLine("usage: add-device <OrderNumber> <Name> [fw ...]");
            Console.WriteLine("  e.g. add-device \"6ES7 511-1AK02-0AB0\" PLC_1 V3.1 V3.0 V2.9");
            return 1;
        }
        string order = a[0], name = a[1];
        var firmwares = a.Length > 2
            ? a.Skip(2).ToArray()
            : new[] { "V3.1", "V3.0", "V2.9", "V2.8" };

        foreach (string fw in firmwares)
        {
            string tid = "OrderNumber:" + order + "/" + fw;
            try
            {
                Console.WriteLine("trying " + tid);
                project.Devices.CreateWithItem(tid, name, name);
                Console.WriteLine("created with firmware " + fw);
                project.Save();
                Console.WriteLine("saved");
                return 0;
            }
            catch (Exception ex)
            {
                // A firmware the installation does not have simply is not found; keep going.
                Console.WriteLine("  failed: " + Full(ex));
            }
        }
        Console.WriteLine("no firmware variant worked - check the article number and what is installed");
        return 3;
    }

    static int CmdProjectSet(Project project, string[] a)
    {
        if (a.Length < 2) { Console.WriteLine("usage: project-set <Attr> <value>"); return 1; }
        SetAttribute((IEngineeringObject)project, a[0], a[1]);
        project.Save();
        Console.WriteLine("saved");
        return 0;
    }

    static int CmdPlug(Project project, string[] a)
    {
        if (a.Length < 3) { Console.WriteLine("usage: plug <slot> <OrderNumber> <Name> [fw ...]"); return 1; }
        int slot = int.Parse(a[0]);
        string order = a[1], name = a[2];
        var firmwares = a.Length > 3 ? a.Skip(3).ToArray() : new[] { "-", "V2.1", "V2.0", "V1.1", "V1.0", "V0.0" };
        var dev = FirstDevice(project);
        // the rack is the device item that accepts the module at that slot
        var racks = new List<DeviceItem>();
        foreach (var top in dev.DeviceItems) { racks.Add(top); foreach (var c in top.DeviceItems) racks.Add(c); }
        foreach (string fw in firmwares)
        {
            string tid = "OrderNumber:" + order + (fw == "-" ? "" : "/" + fw);
            foreach (var rack in racks)
            {
                try
                {
                    if (!rack.CanPlugNew(tid, name, slot)) continue;
                    rack.PlugNew(tid, name, slot);
                    Console.WriteLine("plugged " + tid + " into " + rack.Name + " slot " + slot);
                    project.Save();
                    Console.WriteLine("saved");
                    return 0;
                }
                catch (Exception ex)
                {
                    Console.WriteLine("  " + tid + " on " + rack.Name + ": " + Full(ex));
                }
            }
            Console.WriteLine("  not pluggable: " + tid);
        }
        Console.WriteLine("no variant could be plugged");
        return 3;
    }

    static string Full(Exception ex)
    {
        var sb = new System.Text.StringBuilder();
        for (var e = ex; e != null; e = e.InnerException)
            sb.Append(" | ").Append(e.GetType().Name).Append(": ").Append(e.Message.Replace("\r", " ").Replace("\n", " "));
        return sb.ToString();
    }
}
