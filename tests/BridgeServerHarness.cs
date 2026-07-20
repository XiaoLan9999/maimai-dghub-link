using System;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;

namespace MelonLoader
{
    [AttributeUsage(AttributeTargets.Assembly)]
    public sealed class MelonInfoAttribute : Attribute
    {
        public MelonInfoAttribute(Type type, string name, string version, string author, string link) { }
    }

    [AttributeUsage(AttributeTargets.Assembly)]
    public sealed class MelonGameAttribute : Attribute
    {
        public MelonGameAttribute(string developer, string game) { }
    }

    public class MelonMod
    {
        public virtual void OnInitializeMelon() { }
        public virtual void OnUpdate() { }
        public virtual void OnApplicationQuit() { }
        public virtual void OnDeinitializeMelon() { }
    }

    public static class MelonLogger
    {
        public static void Msg(string value) { }
        public static void Error(string value) { }
        public static void Warning(string value) { }
    }
}

namespace HarmonyLib
{
    public sealed class Harmony
    {
        public Harmony(string id) { }
        public void Patch(
            System.Reflection.MethodBase original,
            HarmonyMethod prefix,
            HarmonyMethod postfix) { }
    }

    public sealed class HarmonyMethod
    {
        public HarmonyMethod(System.Reflection.MethodInfo method) { }
    }

    public static class AccessTools
    {
        public static Type TypeByName(string name)
        {
            return Type.GetType(name);
        }

        public static System.Reflection.MethodInfo Method(
            Type type,
            string name,
            Type[] parameters = null)
        {
            return type.GetMethod(
                name,
                System.Reflection.BindingFlags.Public |
                System.Reflection.BindingFlags.NonPublic |
                System.Reflection.BindingFlags.Static |
                System.Reflection.BindingFlags.Instance,
                null,
                parameters ?? Type.EmptyTypes,
                null);
        }
    }
}

namespace Manager
{
    public static class GameManager
    {
        public static bool IsInGame;
        public static uint MusicTrackNumber;
    }

    public sealed class GamePlayManager
    {
        public static readonly GamePlayManager Instance = new GamePlayManager();
        public GameScoreList GetGameScore(int player, int track) { return null; }
    }

    public sealed class GameScoreList
    {
        public bool IsEnable;
        public uint CriticalNum;
        public uint PerfectNum;
        public uint GreatNum;
        public uint GoodNum;
        public uint MissNum;
        public uint Combo;
        public uint DxScore;
        public decimal GetAchivement() { return 0m; }
    }

    public struct JudgeResultSt
    {
        public void UpdateScore(int monitorIndex, NoteScore.EScoreType type, NoteJudge.ETiming timing) { }
    }
}

public static class NoteScore
{
    public enum EScoreType { Tap, Hold, Slide, Break, Touch }
}

public static class NoteJudge
{
    public enum ETiming { TooFast, Critical, TooLate }
    public enum JudgeBox { Miss, Good, Great, Perfect, Critical, End }
    public static JudgeBox ConvertJudge(ETiming timing) { return JudgeBox.Critical; }
}

internal static class BridgeServerHarness
{
    public static int Main()
    {
        MaiDGBridge.Snapshot snapshot = new MaiDGBridge.Snapshot
        {
            Player = 1,
            Track = 2,
            Title = "quote \" and newline\n",
            Artist = "测试",
            Chart = "MASTER",
            Level = "13+",
            Progress = 0.5m
        };
        string json = snapshot.ToJson("counts", "PLAYING");
        if (!json.Contains("quote \\\" and newline\\n") ||
            !json.Contains("\"progress\":0.5000"))
        {
            throw new Exception("snapshot metadata JSON escaping failed: " + json);
        }

        MaiDGBridge.PresenceSnapshot presence = new MaiDGBridge.PresenceSnapshot
        {
            Status = "SELECTING",
            Version = "1.55.00",
            Remaining = 42,
            MusicId = 12345,
            DifficultyId = 3,
            Difficulty = "MASTER",
            Title = "quote \" test",
            Artist = "测试"
        };
        string presenceJson = presence.ToJson();
        if (!presenceJson.Contains("\"event\":\"presence\"") ||
            !presenceJson.Contains("\"remaining\":42") ||
            !presenceJson.Contains("quote \\\" test"))
        {
            throw new Exception("presence JSON failed: " + presenceJson);
        }

        TcpListener probe = new TcpListener(IPAddress.Loopback, 0);
        probe.Start();
        int port = ((IPEndPoint)probe.LocalEndpoint).Port;
        probe.Stop();

        MaiDGBridge.SseServer server = new MaiDGBridge.SseServer(port);
        server.Start();
        try
        {
            TcpClient client = new TcpClient();
            client.ReceiveTimeout = 3000;
            client.Connect(IPAddress.Loopback, port);
            NetworkStream stream = client.GetStream();
            byte[] request = Encoding.ASCII.GetBytes(
                "GET /events HTTP/1.1\r\nHost: 127.0.0.1\r\nAccept: text/event-stream\r\n\r\n");
            stream.Write(request, 0, request.Length);

            StreamReader reader = new StreamReader(stream, Encoding.UTF8);
            string line;
            bool sawOk = false;
            while (!string.IsNullOrEmpty(line = reader.ReadLine()))
            {
                if (line == "HTTP/1.1 200 OK")
                {
                    sawOk = true;
                }
            }
            if (!sawOk || reader.ReadLine() != ": connected" || reader.ReadLine() != "")
            {
                throw new Exception("invalid SSE handshake");
            }

            Thread.Sleep(100);
            server.PublishJson("{\"test\":1}");
            if (reader.ReadLine() != "data: {\"test\":1}" || reader.ReadLine() != "")
            {
                throw new Exception("invalid SSE event");
            }

            client.Close();
            Console.WriteLine("bridge server ok: loopback HTTP, SSE handshake, event broadcast");
            return 0;
        }
        finally
        {
            server.Stop();
        }
    }
}
