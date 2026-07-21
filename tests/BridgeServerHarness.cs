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
        public int GetGameScoreCalls;
        public readonly GameScoreList[] Scores = { new GameScoreList(), new GameScoreList() };
        public GameScoreList GetGameScore(int player, int track)
        {
            GetGameScoreCalls++;
            return Scores[player];
        }
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
        public decimal Achievement;
        public decimal GetAchivement() { return Achievement; }
    }

    public sealed class NotesManager
    {
        private static readonly NotesManager[] Instances = { new NotesManager(), new NotesManager() };
        private static float CurrentMsec;
        public uint PlayFirstMsec;
        public uint PlayFinalMsec;
        public static NotesManager Instance(int player) { return Instances[player]; }
        public static float GetCurrentMsec() { return CurrentMsec; }
        public uint getPlayFirstMsec() { return PlayFirstMsec; }
        public uint getPlayFinalMsec() { return PlayFinalMsec; }
        public static void SetTime(int player, float currentMsec, uint firstMsec, uint finalMsec)
        {
            CurrentMsec = currentMsec;
            Instances[player].PlayFirstMsec = firstMsec;
            Instances[player].PlayFinalMsec = finalMsec;
        }
    }

    public sealed class UserDataManager
    {
        public static readonly UserDataManager Instance = new UserDataManager();
        private readonly UserData[] _users = { new UserData(), new UserData() };
        public UserData GetUserData(long index) { return _users[index]; }
        public void SetUserNames(string first, string second)
        {
            _users[0].Detail.UserName = first;
            _users[1].Detail.UserName = second;
        }
    }

    public sealed class UserData
    {
        public bool IsEntry = true;
        public UserDatas.UserDetail Detail = new UserDatas.UserDetail();
    }

    public struct JudgeResultSt
    {
        public void UpdateScore(int monitorIndex, NoteScore.EScoreType type, NoteJudge.ETiming timing) { }
    }
}

namespace Manager.UserDatas
{
    public sealed class UserDetail
    {
        public string UserName = "Player42";
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

namespace MAI2System
{
    public sealed class Config
    {
        public string displayVersionString = "Ver.CN1.56-B";
    }

    public sealed class SystemConfig
    {
        public static readonly SystemConfig Instance = new SystemConfig();
        public readonly Config config = new Config();
    }
}

internal static class BridgeServerHarness
{
    private sealed class FakeSelectProcess
    {
        public int[] CurrentDifficulty = { 3, 3 };
    }

    private sealed class FakeSelectedMusic
    {
        public int Difficulty = 4;
    }

    private class FakeRuntimeSelectProcess
    {
        public bool IsLevelTab(int musicIndex)
        {
            return false;
        }

        public bool IsExtraFolder(int index)
        {
            return false;
        }

        public int GetDifficultySelectIndex(int player)
        {
            return 1;
        }

        public int GetCurrentDifficulty(int player)
        {
            return 2;
        }
    }

    private sealed class FakeLevelSelectProcess : FakeRuntimeSelectProcess
    {
        public new bool IsLevelTab(int musicIndex)
        {
            return true;
        }
    }

    private sealed class FakeGameResolvedSelectProcess
    {
        public int GetDifficulty(int playerIndex, int musicIndex)
        {
            return 4;
        }

        public int GetCurrentDifficulty(int playerIndex)
        {
            return 2;
        }
    }

    private sealed class FakeStringId
    {
        public int id;
        public string str;

        public FakeStringId(int value, string text)
        {
            id = value;
            str = text;
        }
    }

    private sealed class FakeUtageMusic
    {
        public FakeStringId name = new FakeStringId(111234, "[Star] Test Utage");
        public FakeStringId genreName = new FakeStringId(107, "Utage");
        public string utageKanjiName = "X";
    }

    private sealed class FakeEmptyAuthor
    {
        public FakeStringId notesDesigner = new FakeStringId(0, string.Empty);
    }

    private sealed class FakeResultScore
    {
        public uint CriticalNum = 1;
        public uint PerfectNum = 2;
        public uint GreatNum = 3;
        public uint GoodNum = 4;
        public uint MissNum = 5;
        public uint Combo = 2;
        public uint DxScore = 123;

        public decimal GetAchivement()
        {
            return 87.6543m;
        }
    }

    private sealed class FakeResultProcess
    {
        private readonly FakeResultScore[] _gameScoreLists = { new FakeResultScore(), null };
        private readonly int _musicID = 24680;
    }

    public static int Main()
    {
        System.Reflection.MethodInfo readVersion = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ReadVersion",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        string version = (string)readVersion.Invoke(null, null);
        if (version != "Ver.CN1.56-B")
        {
            throw new Exception("version lookup failed: " + version);
        }

        System.Reflection.MethodInfo readDifficulty = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ReadSelectedDifficulty",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        int selectedDifficulty = (int)readDifficulty.Invoke(
            null, new object[] { new FakeSelectProcess(), new FakeSelectedMusic() });
        int fallbackDifficulty = (int)readDifficulty.Invoke(
            null, new object[] { new FakeSelectProcess(), new object() });
        if (selectedDifficulty != 4 || fallbackDifficulty != 3)
        {
            throw new Exception("selected difficulty resolution failed");
        }
        int runtimeDifficulty = (int)readDifficulty.Invoke(
            null, new object[] { new FakeRuntimeSelectProcess(), new FakeSelectedMusic() });
        if (runtimeDifficulty != 2)
        {
            throw new Exception("runtime difficulty resolution failed");
        }
        int levelDifficulty = (int)readDifficulty.Invoke(
            null, new object[] { new FakeLevelSelectProcess(), new FakeSelectedMusic() });
        if (levelDifficulty != 1)
        {
            throw new Exception("level difficulty resolution failed");
        }
        int gameResolvedDifficulty = (int)readDifficulty.Invoke(
            null, new object[] { new FakeGameResolvedSelectProcess(), new FakeSelectedMusic() });
        if (gameResolvedDifficulty != 4)
        {
            throw new Exception("game difficulty resolver was not preferred");
        }

        System.Reflection.MethodInfo readStringId = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ReadStringId", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.MethodInfo isGuestName = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "IsGuestName", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        if (!(bool)isGuestName.Invoke(null, new object[] { "\uff27\uff35\uff25\uff33\uff34" }) ||
            (bool)isGuestName.Invoke(null, new object[] { "Player42" }))
        {
            throw new Exception("guest name normalization failed");
        }
        string emptyAuthor = (string)readStringId.Invoke(
            null, new object[] { new FakeEmptyAuthor(), "notesDesigner" });
        if (emptyAuthor != string.Empty)
        {
            throw new Exception("empty StringID leaked its runtime type name");
        }
        FakeUtageMusic fakeUtage = new FakeUtageMusic();
        System.Reflection.MethodInfo isUtageMusic = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "IsUtageMusic", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.MethodInfo utageChartName = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "UtageChartName", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        if (!(bool)isUtageMusic.Invoke(null, new object[] { fakeUtage, 111234 }) ||
            (string)utageChartName.Invoke(null, new object[] { fakeUtage }) != "UTAGE X")
        {
            throw new Exception("utage metadata detection failed");
        }

        System.Reflection.MethodInfo captureResult = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "CaptureResult",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        MaiDGBridge.Snapshot result = (MaiDGBridge.Snapshot)captureResult.Invoke(
            new MaiDGBridge.BridgeMod(), new object[] { new FakeResultProcess(), 0 });
        if (result == null || result.MusicId != 24680 || result.Critical != 1 ||
            result.Perfect != 2 || result.Great != 3 || result.Good != 4 || result.Miss != 5 ||
            result.Achievement != 87.6543m || !result.ToJson("settle", "RESULT").Contains("\"event\":\"settle\""))
        {
            throw new Exception("result snapshot capture failed");
        }

        System.Reflection.FieldInfo sessionStarted = typeof(MaiDGBridge.BridgeMod).GetField(
            "_sessionStarted",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.MethodInfo capturePresence = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "CapturePresence",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        MaiDGBridge.BridgeMod bridge = new MaiDGBridge.BridgeMod();
        System.Reflection.MethodInfo shouldCapturePresence = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ShouldCapturePresence",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo presenceRefreshRequested = typeof(MaiDGBridge.BridgeMod).GetField(
            "_presenceRefreshRequested",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo lastPresencePublish = typeof(MaiDGBridge.BridgeMod).GetField(
            "_lastPresencePublish",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo presenceInterval = typeof(MaiDGBridge.BridgeMod).GetField(
            "_presenceIntervalMs",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        presenceRefreshRequested.SetValue(bridge, false);
        lastPresencePublish.SetValue(bridge, 1000L);
        presenceInterval.SetValue(bridge, 250);
        if ((bool)shouldCapturePresence.Invoke(bridge, new object[] { 1100L }))
        {
            throw new Exception("presence refresh ignored its polling interval");
        }
        presenceRefreshRequested.SetValue(bridge, true);
        if (!(bool)shouldCapturePresence.Invoke(bridge, new object[] { 1101L }) ||
            (bool)shouldCapturePresence.Invoke(bridge, new object[] { 1102L }) ||
            !(bool)shouldCapturePresence.Invoke(bridge, new object[] { 1351L }))
        {
            throw new Exception("event-driven presence refresh scheduling failed");
        }
        System.Reflection.MethodInfo shouldCaptureResult = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ShouldCaptureResult",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo resultRefreshRequested = typeof(MaiDGBridge.BridgeMod).GetField(
            "_resultRefreshRequested",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo lastResultPublish = typeof(MaiDGBridge.BridgeMod).GetField(
            "_lastResultPublish",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo resultInterval = typeof(MaiDGBridge.BridgeMod).GetField(
            "_publishIntervalMs",
            System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        resultRefreshRequested.SetValue(bridge, false);
        lastResultPublish.SetValue(bridge, 2000L);
        resultInterval.SetValue(bridge, 250);
        if ((bool)shouldCaptureResult.Invoke(bridge, new object[] { 2100L }))
        {
            throw new Exception("result refresh ignored its polling interval");
        }
        resultRefreshRequested.SetValue(bridge, true);
        if (!(bool)shouldCaptureResult.Invoke(bridge, new object[] { 2101L }) ||
            (bool)shouldCaptureResult.Invoke(bridge, new object[] { 2102L }) ||
            !(bool)shouldCaptureResult.Invoke(bridge, new object[] { 2351L }))
        {
            throw new Exception("event-driven result refresh scheduling failed");
        }
        sessionStarted.SetValue(null, false);
        MaiDGBridge.PresenceSnapshot preLogin =
            (MaiDGBridge.PresenceSnapshot)capturePresence.Invoke(bridge, null);
        sessionStarted.SetValue(null, true);
        MaiDGBridge.PresenceSnapshot loading =
            (MaiDGBridge.PresenceSnapshot)capturePresence.Invoke(bridge, null);
        sessionStarted.SetValue(null, false);
        if (preLogin.Status != "MENU" || preLogin.UserName != string.Empty || loading.Status != "LOADING")
        {
            throw new Exception("session presence transition failed");
        }

        System.Reflection.FieldInfo activeBridge = typeof(MaiDGBridge.BridgeMod).GetField(
            "_active", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.FieldInfo cachedUserName = typeof(MaiDGBridge.BridgeMod).GetField(
            "_cachedUserName", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.MethodInfo activateSession = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "ActivateSession", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.MethodInfo advertiseStart = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "AdvertiseStartPostfix", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        System.Reflection.MethodInfo advertiseRelease = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "AdvertiseReleasePostfix", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Static);
        activeBridge.SetValue(null, bridge);
        Manager.UserDataManager.Instance.SetUserNames("\u6e38\u5ba2", "Player42");
        activateSession.Invoke(null, null);
        if (!(bool)sessionStarted.GetValue(null) || (string)cachedUserName.GetValue(bridge) != "Player42")
        {
            throw new Exception("post-login identity activation did not skip the guest slot");
        }
        object advertise = new object();
        advertiseStart.Invoke(null, new object[] { advertise });
        MaiDGBridge.PresenceSnapshot returnedMenu =
            (MaiDGBridge.PresenceSnapshot)capturePresence.Invoke(bridge, null);
        if (returnedMenu.Status != "MENU" || returnedMenu.UserName != string.Empty ||
            (bool)sessionStarted.GetValue(null))
        {
            throw new Exception("main-menu session reset failed");
        }
        advertiseRelease.Invoke(null, new object[] { advertise });
        activeBridge.SetValue(null, null);

        TcpListener gameplayProbe = new TcpListener(IPAddress.Loopback, 0);
        gameplayProbe.Start();
        int gameplayPort = ((IPEndPoint)gameplayProbe.LocalEndpoint).Port;
        gameplayProbe.Stop();
        MaiDGBridge.SseServer gameplayServer = new MaiDGBridge.SseServer(gameplayPort);
        System.Reflection.FieldInfo bridgeServer = typeof(MaiDGBridge.BridgeMod).GetField(
            "_server", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.MethodInfo onJudgeResult = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "OnJudgeResult", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.MethodInfo cacheSelectedMetadata = typeof(MaiDGBridge.BridgeMod).GetMethod(
            "CacheSelectedMetadata", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo hookCounts = typeof(MaiDGBridge.BridgeMod).GetField(
            "_hookCounts", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        System.Reflection.FieldInfo judgePublishPending = typeof(MaiDGBridge.BridgeMod).GetField(
            "_judgePublishPending", System.Reflection.BindingFlags.NonPublic | System.Reflection.BindingFlags.Instance);
        gameplayServer.Start();
        try
        {
            bridgeServer.SetValue(bridge, gameplayServer);
            Manager.GameManager.IsInGame = true;
            Manager.GameManager.MusicTrackNumber = 1;
            Manager.GamePlayManager.Instance.GetGameScoreCalls = 0;
            Manager.GamePlayManager.Instance.Scores[0].IsEnable = true;
            Manager.GamePlayManager.Instance.Scores[0].DxScore = 1234;
            Manager.GamePlayManager.Instance.Scores[0].Achievement = 58.2657m;
            Manager.NotesManager.SetTime(0, 61000f, 1000, 121000);
            cacheSelectedMetadata.Invoke(bridge, new object[] { new MaiDGBridge.PresenceSnapshot
            {
                MusicId = 24680,
                DifficultyId = 4,
                Difficulty = "Re:MASTER",
                Title = "Cached Song",
                Artist = "Cached Artist"
            } });
            for (int frame = 0; frame < 60; frame++)
            {
                bridge.OnUpdate();
            }
            for (int touch = 0; touch < 64; touch++)
            {
                onJudgeResult.Invoke(
                    bridge,
                    new object[] { 0, NoteScore.EScoreType.Touch, NoteJudge.ETiming.Critical });
            }
            MaiDGBridge.Snapshot[] hooked = (MaiDGBridge.Snapshot[])hookCounts.GetValue(bridge);
            bool[] pending = (bool[])judgePublishPending.GetValue(bridge);
            if (Manager.GamePlayManager.Instance.GetGameScoreCalls != 0 ||
                hooked[0] == null || hooked[0].Critical != 64 || hooked[0].Title != "Cached Song" ||
                !pending[0])
            {
                throw new Exception("pre-judgement zero-poll capture or cached metadata failed");
            }
            bridge.OnUpdate();
            for (int frame = 0; frame < 60; frame++)
            {
                bridge.OnUpdate();
            }
            if (pending[0] || Manager.GamePlayManager.Instance.GetGameScoreCalls != 1 ||
                hooked[0].DxScore != 1234 || hooked[0].Achievement != 58.2657m ||
                hooked[0].Progress != 0.5m || hooked[0].ElapsedSeconds != 60 ||
                hooked[0].DurationSeconds != 120)
            {
                throw new Exception("dense judgement batching or one-second gameplay metrics sampling failed");
            }
        }
        finally
        {
            Manager.GameManager.IsInGame = false;
            bridgeServer.SetValue(bridge, null);
            gameplayServer.Stop();
        }

        MaiDGBridge.Snapshot snapshot = new MaiDGBridge.Snapshot
        {
            Player = 1,
            Track = 2,
            Version = "Ver.CN1.56-B",
            UserName = "玩家",
            Title = "quote \" and newline\n",
            Artist = "测试",
            Chart = "MASTER",
            Level = "13+",
            Progress = 0.5m,
            ElapsedSeconds = 60,
            DurationSeconds = 120
        };
        string json = snapshot.ToJson("counts", "PLAYING");
        if (!json.Contains("quote \\\" and newline\\n") ||
            !json.Contains("\"progress\":0.5000") ||
            !json.Contains("\"elapsed_seconds\":60") ||
            !json.Contains("\"duration_seconds\":120") ||
            !json.Contains("\"version\":\"Ver.CN1.56-B\"") ||
            !json.Contains("\"user_name\":\"玩家\""))
        {
            throw new Exception("snapshot metadata JSON escaping failed: " + json);
        }

        MaiDGBridge.PresenceSnapshot presence = new MaiDGBridge.PresenceSnapshot
        {
            Status = "SELECTING",
            Version = "1.55.00",
            UserName = "小\"蓝",
            Remaining = 42,
            MusicId = 12345,
            DifficultyId = 3,
            Difficulty = "MASTER",
            Title = "quote \" test",
            Artist = "测试",
            Author = "谱\n师",
            Composer = "曲师",
            Level = "14+",
            Constant = 14.0m,
            GameDifficultyId = 3,
            CurrentDifficultyId = 3,
            SelectDifficultyIndex = 1,
            CardDifficultyId = 3,
            IsLevelTab = true
        };
        string presenceJson = presence.ToJson();
        if (!presenceJson.Contains("\"event\":\"presence\"") ||
            !presenceJson.Contains("\"remaining\":42") ||
            !presenceJson.Contains("quote \\\" test") ||
            !presenceJson.Contains("\"user_name\":\"小\\\"蓝\"") ||
            !presenceJson.Contains("\"constant\":14.0") ||
            !presenceJson.Contains("\"debug_game_difficulty\":3") ||
            !presenceJson.Contains("\"debug_level_tab\":true") ||
            !presenceJson.Contains("谱\\n师"))
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
