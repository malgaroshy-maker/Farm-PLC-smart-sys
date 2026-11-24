// PlcsimBridge - lets the Python farm model (apps/simulator/src/plcsim_plant.py) read the virtual
// PLC's outputs and write its inputs through the PLCSIM Advanced API. No Python package needed.
//
//   PlcsimBridge.exe <instance-name> [port=1600]
//
// Listens on 127.0.0.1 only. One request per line, one answer per line:
//   X <op>|<op>|...      ops: "R <tag> <type>" or "W <tag> <type> <value>"
//                        types: bool, u8, i16, i32, f32. Answer: values joined by '|' ("ok" for writes)
//   S                    operating state (Run, Stop, ...)
// Errors answer "ERR <message>". The PLCSIM API is not Openness: TIA asks for no approval.
//
// Build (no SDK needed):
//   csc -platform:x64 -out:PlcsimBridge.exe -r:"<PLCSIMADV API>\Siemens.Simatic.Simulation.Runtime.Api.x64.dll" PlcsimBridge.cs

using System;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using Siemens.Simatic.Simulation.Runtime;

static class Program
{
    static readonly string ApiDir = FindApi();

    static string FindApi()
    {
        string root = @"C:\Program Files (x86)\Common Files\Siemens\PLCSIMADV\API";
        if (!Directory.Exists(root)) return null;
        return Directory.GetDirectories(root).OrderByDescending(d => d, StringComparer.Ordinal).FirstOrDefault();
    }

    static Assembly Resolve(object s, ResolveEventArgs e)
    {
        try
        {
            string n = new AssemblyName(e.Name).Name;
            if (ApiDir == null || string.IsNullOrEmpty(n) || n.IndexOfAny(Path.GetInvalidFileNameChars()) >= 0) return null;
            string dll = Path.Combine(ApiDir, n + ".dll");
            return File.Exists(dll) ? Assembly.LoadFrom(dll) : null;
        }
        catch { return null; }
    }

    static int Main(string[] args)
    {
        AppDomain.CurrentDomain.AssemblyResolve += Resolve;
        if (args.Length < 1) { Console.WriteLine("usage: PlcsimBridge <instance-name> [port]"); return 1; }
        int port = args.Length > 1 ? int.Parse(args[1]) : 1600;
        return Run(args[0], port);
    }

    [System.Runtime.CompilerServices.MethodImpl(System.Runtime.CompilerServices.MethodImplOptions.NoInlining)]
    static int Run(string name, int port)
    {
        IInstance inst;
        try
        {
            inst = SimulationRuntimeManager.CreateInterface(name);
            inst.UpdateTagList();
        }
        catch (Exception ex)
        {
            Console.WriteLine("ERROR cannot attach to PLCSIM instance '" + name + "': " + ex.Message);
            return 2;
        }
        Console.WriteLine("attached to '" + name + "' (" + inst.OperatingState + "), listening on 127.0.0.1:" + port);
        var lockObj = new object();
        var listener = new TcpListener(IPAddress.Loopback, port);
        listener.Start();
        while (true)
        {
            var client = listener.AcceptTcpClient();
            new Thread(() => Serve(client, inst, lockObj)) { IsBackground = true }.Start();
        }
    }

    static void Serve(TcpClient client, IInstance inst, object lockObj)
    {
        using (client)
        using (var stream = client.GetStream())
        using (var reader = new StreamReader(stream, Encoding.ASCII))
        using (var writer = new StreamWriter(stream, Encoding.ASCII) { AutoFlush = true, NewLine = "\n" })
        {
            string line;
            while ((line = reader.ReadLine()) != null)
            {
                string answer;
                lock (lockObj)
                {
                    try { answer = Handle(line.Trim(), inst); }
                    catch (Exception ex)
                    {
                        answer = "ERR " + ex.Message.Replace('\n', ' ');
                        // a new download changes the tag list: refresh it once and let the caller retry
                        try { inst.UpdateTagList(); } catch { }
                    }
                }
                writer.WriteLine(answer);
            }
        }
    }

    static string Handle(string line, IInstance inst)
    {
        if (line == "S") return inst.OperatingState.ToString();
        if (!line.StartsWith("X ")) return "ERR unknown request";
        var parts = line.Substring(2).Split('|');
        var outv = new string[parts.Length];
        for (int i = 0; i < parts.Length; i++)
        {
            var p = parts[i].Trim().Split(' ');
            if (p.Length < 3) throw new ArgumentException("bad op: " + parts[i]);
            string tag = p[1], type = p[2];
            if (p[0] == "R") outv[i] = Read(inst, tag, type);
            else if (p[0] == "W" && p.Length >= 4) { Write(inst, tag, type, p[3]); outv[i] = "ok"; }
            else throw new ArgumentException("bad op: " + parts[i]);
        }
        return string.Join("|", outv);
    }

    static string Read(IInstance inst, string tag, string type)
    {
        switch (type)
        {
            case "bool": return inst.ReadBool(tag) ? "1" : "0";
            case "u8": return inst.ReadUInt8(tag).ToString(CultureInfo.InvariantCulture);
            case "i16": return inst.ReadInt16(tag).ToString(CultureInfo.InvariantCulture);
            case "i32": return inst.ReadInt32(tag).ToString(CultureInfo.InvariantCulture);
            case "f32": return inst.ReadFloat(tag).ToString("R", CultureInfo.InvariantCulture);
            default: throw new ArgumentException("bad type " + type);
        }
    }

    static void Write(IInstance inst, string tag, string type, string v)
    {
        var ci = CultureInfo.InvariantCulture;
        switch (type)
        {
            case "bool": inst.WriteBool(tag, v == "1" || v == "true"); break;
            case "u8": inst.WriteUInt8(tag, byte.Parse(v, ci)); break;
            case "i16": inst.WriteInt16(tag, short.Parse(v, ci)); break;
            case "i32": inst.WriteInt32(tag, int.Parse(v, ci)); break;
            case "f32": inst.WriteFloat(tag, float.Parse(v, ci)); break;
            default: throw new ArgumentException("bad type " + type);
        }
    }
}
