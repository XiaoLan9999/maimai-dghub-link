using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Globalization;
using System.IO;
using System.Net;
using System.Net.Sockets;
using System.Reflection;
using System.Text;
using System.Threading;
using HarmonyLib;
using Manager;
using MelonLoader;

[assembly: MelonInfo(typeof(MaiDGBridge.BridgeMod), "MaiDGBridge", "1.3.0", "XiaoLan9999", "")]
[assembly: MelonGame("sega-interactive", "Sinmai")]

namespace MaiDGBridge
{
    public sealed class BridgeMod : MelonMod
    {
        private readonly Snapshot[] _last = new Snapshot[2];
        private readonly Snapshot[] _hookCounts = new Snapshot[2];
        private readonly Stopwatch _clock = Stopwatch.StartNew();
        private static BridgeMod _active;
        private SseServer _server;
        private bool _wasInGame;
        private bool _judgeHookObserved;
        private bool _metadataWarningLogged;
        private long _lastPeriodicPublish;
        private long _lastErrorLog;
        private int _publishIntervalMs = 250;

        public override void OnInitializeMelon()
        {
            _active = this;
            BridgeConfig config = BridgeConfig.Load(Path.Combine(Environment.CurrentDirectory, "MaiDGBridge.ini"));
            _publishIntervalMs = config.PublishIntervalMs;

            if (!config.Enabled)
            {
                MelonLogger.Msg("MaiDGBridge is disabled by MaiDGBridge.ini");
                return;
            }

            try
            {
                _server = new SseServer(config.Port);
                _server.Start();
                PatchJudgeResults();
                MelonLogger.Msg("MaiDGBridge listening on http://127.0.0.1:" + config.Port + "/events");
            }
            catch (Exception ex)
            {
                MelonLogger.Error("MaiDGBridge failed to start: " + ex.Message);
                _server = null;
            }
        }

        public override void OnUpdate()
        {
            if (_server == null || !_server.IsRunning)
            {
                return;
            }

            try
            {
                bool inGame = GameManager.IsInGame;
                long now = _clock.ElapsedMilliseconds;

                if (inGame)
                {
                    if (!_wasInGame)
                    {
                        _last[0] = null;
                        _last[1] = null;
                        _server.PublishJson("{\"event\":\"state\",\"status\":\"PLAYING\"}");
                    }

                    bool periodic = now - _lastPeriodicPublish >= _publishIntervalMs;
                    for (int player = 0; player < 2; player++)
                    {
                        Snapshot current = Capture(player, periodic);
                        if (current != null && (periodic || !current.SameValues(_last[player])))
                        {
                            _server.PublishJson(current.ToJson("counts", "PLAYING"));
                        }
                        if (current != null)
                        {
                            _last[player] = current;
                        }
                    }

                    if (periodic)
                    {
                        _lastPeriodicPublish = now;
                    }
                }
                else if (_wasInGame)
                {
                    for (int player = 0; player < 2; player++)
                    {
                        Snapshot result = _last[player];
                        if (result != null && result.TotalJudgements > 0)
                        {
                            _server.PublishJson(result.ToJson("settle", "RESULT"));
                        }
                        _last[player] = null;
                    }
                    _server.PublishJson("{\"event\":\"state\",\"status\":\"IDLE\"}");
                }

                _wasInGame = inGame;
            }
            catch (Exception ex)
            {
                long now = _clock.ElapsedMilliseconds;
                if (now - _lastErrorLog >= 5000)
                {
                    MelonLogger.Warning("MaiDGBridge capture error: " + ex.Message);
                    _lastErrorLog = now;
                }
            }
        }

        public override void OnApplicationQuit()
        {
            StopServer();
        }

        public override void OnDeinitializeMelon()
        {
            StopServer();
        }

        private void StopServer()
        {
            if (ReferenceEquals(_active, this))
            {
                _active = null;
            }
            SseServer server = _server;
            _server = null;
            if (server != null)
            {
                server.Stop();
            }
        }

        private void PatchJudgeResults()
        {
            HarmonyLib.Harmony harmony = new HarmonyLib.Harmony("MaiDGBridge.JudgeResultHook");
            System.Reflection.MethodInfo original = AccessTools.Method(
                typeof(JudgeResultSt),
                "UpdateScore",
                new System.Type[] { typeof(int), typeof(NoteScore.EScoreType), typeof(NoteJudge.ETiming) });
            System.Reflection.MethodInfo postfix = AccessTools.Method(
                typeof(BridgeMod),
                "JudgeResultPostfix");
            if (original == null || postfix == null)
            {
                throw new MissingMethodException("JudgeResultSt.UpdateScore hook target was not found");
            }
            harmony.Patch(original, null, new HarmonyMethod(postfix));
            MelonLogger.Msg("MaiDGBridge judge hook installed");
        }

        private static void JudgeResultPostfix(
            int monitorIndex,
            NoteScore.EScoreType type,
            NoteJudge.ETiming timing)
        {
            BridgeMod active = _active;
            if (active != null)
            {
                active.OnJudgeResult(monitorIndex, type, timing);
            }
        }

        private void OnJudgeResult(
            int monitorIndex,
            NoteScore.EScoreType type,
            NoteJudge.ETiming timing)
        {
            if (_server == null || !_server.IsRunning || monitorIndex < 0 || monitorIndex >= 2)
            {
                return;
            }

            uint track = GameManager.MusicTrackNumber;
            Snapshot counts = _hookCounts[monitorIndex];
            if (counts == null || counts.Track != track)
            {
                counts = new Snapshot { Player = monitorIndex + 1, Track = track };
                _hookCounts[monitorIndex] = counts;
                ApplyMetadata(counts, monitorIndex);
            }
            else if (_last[monitorIndex] != null)
            {
                CopyMetadata(_last[monitorIndex], counts);
            }

            switch (NoteJudge.ConvertJudge(timing))
            {
                case NoteJudge.JudgeBox.Miss:
                    counts.Miss++;
                    counts.Combo = 0;
                    break;
                case NoteJudge.JudgeBox.Good:
                    counts.Good++;
                    counts.Combo++;
                    break;
                case NoteJudge.JudgeBox.Great:
                    counts.Great++;
                    counts.Combo++;
                    break;
                case NoteJudge.JudgeBox.Perfect:
                    counts.Perfect++;
                    counts.Combo++;
                    break;
                case NoteJudge.JudgeBox.Critical:
                    counts.Critical++;
                    counts.Combo++;
                    break;
                default:
                    return;
            }

            if (!_judgeHookObserved)
            {
                _judgeHookObserved = true;
                MelonLogger.Msg("MaiDGBridge received its first live judgement");
            }
            _server.PublishJson(counts.ToJson("counts", "PLAYING"));
        }

        private Snapshot Capture(int player, bool refreshMetadata)
        {
            GameScoreList score = GamePlayManager.Instance.GetGameScore(player, -1);
            if (score == null || !score.IsEnable)
            {
                return null;
            }

            Snapshot snapshot = new Snapshot
            {
                Player = player + 1,
                Track = GameManager.MusicTrackNumber,
                Critical = score.CriticalNum,
                Perfect = score.PerfectNum,
                Great = score.GreatNum,
                Good = score.GoodNum,
                Miss = score.MissNum,
                Combo = score.Combo,
                DxScore = score.DxScore,
                Achievement = score.GetAchivement()
            };
            if (refreshMetadata || _last[player] == null || _last[player].Track != snapshot.Track)
            {
                ApplyMetadata(snapshot, player);
            }
            else
            {
                CopyMetadata(_last[player], snapshot);
            }
            return snapshot;
        }

        private static void CopyMetadata(Snapshot source, Snapshot target)
        {
            target.MusicId = source.MusicId;
            target.Difficulty = source.Difficulty;
            target.Title = source.Title;
            target.Artist = source.Artist;
            target.Chart = source.Chart;
            target.Level = source.Level;
            target.Constant = source.Constant;
            target.Progress = source.Progress;
        }

        private void ApplyMetadata(Snapshot snapshot, int player)
        {
            try
            {
                System.Type notesManagerType = AccessTools.TypeByName("Manager.NotesManager");
                if (notesManagerType == null)
                {
                    return;
                }

                MethodInfo instanceMethod = notesManagerType.GetMethod(
                    "Instance",
                    BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static,
                    null,
                    new System.Type[] { typeof(int) },
                    null);
                if (instanceMethod == null)
                {
                    return;
                }
                object notesManager = instanceMethod.Invoke(null, new object[] { player });
                if (notesManager == null)
                {
                    return;
                }

                MethodInfo sessionMethod = FindMethod(notesManagerType, "GetSessionInfo", false);
                object session = sessionMethod == null ? null : sessionMethod.Invoke(notesManager, null);
                if (session == null)
                {
                    return;
                }

                snapshot.MusicId = ToInt(ReadMember(session, "musicId"));
                snapshot.Difficulty = ToInt(ReadMember(session, "difficulty"));
                snapshot.Chart = DifficultyName(snapshot.Difficulty);

                MethodInfo progressMethod = FindMethod(notesManagerType, "getPlayProgress", false);
                if (progressMethod != null)
                {
                    snapshot.Progress = ToDecimal(progressMethod.Invoke(notesManager, null));
                    if (snapshot.Progress < 0m)
                    {
                        snapshot.Progress = 0m;
                    }
                    else if (snapshot.Progress > 1m)
                    {
                        snapshot.Progress = 1m;
                    }
                }

                object notes = ReadMember(session, "notesData");
                System.Type dataManagerType = AccessTools.TypeByName("Manager.DataManager");
                object dataManager = ReadStaticMember(dataManagerType, "Instance");
                if (dataManager == null)
                {
                    return;
                }

                MethodInfo getMusic = FindMethod(dataManager.GetType(), "GetMusic", false, typeof(int));
                object music = getMusic == null
                    ? null
                    : getMusic.Invoke(dataManager, new object[] { snapshot.MusicId });
                if (music != null)
                {
                    snapshot.Title = ReadStringId(music, "name");
                    snapshot.Artist = ReadStringId(music, "artistName");
                }

                if (notes != null)
                {
                    int musicLevelId = ToInt(ReadMember(notes, "musicLevelID"));
                    MethodInfo getMusicLevel = FindMethod(
                        dataManager.GetType(), "GetMusicLevel", false, typeof(int));
                    object musicLevel = getMusicLevel == null
                        ? null
                        : getMusicLevel.Invoke(dataManager, new object[] { musicLevelId });
                    snapshot.Constant = ToDecimal(ReadMember(notes, "level")) +
                                        ToDecimal(ReadMember(notes, "levelDecimal")) / 10m;
                    snapshot.Level = ToText(ReadMember(musicLevel, "levelNum"));
                    if (string.IsNullOrEmpty(snapshot.Level) && snapshot.Constant > 0m)
                    {
                        snapshot.Level = snapshot.Constant.ToString(
                            "0.#", CultureInfo.InvariantCulture);
                    }
                }
            }
            catch (Exception ex)
            {
                if (!_metadataWarningLogged)
                {
                    _metadataWarningLogged = true;
                    Exception detail = ex is TargetInvocationException && ex.InnerException != null
                        ? ex.InnerException
                        : ex;
                    MelonLogger.Warning("MaiDGBridge metadata unavailable: " + detail.Message);
                }
            }
        }

        private static MethodInfo FindMethod(
            System.Type type, string name, bool isStatic, params System.Type[] arguments)
        {
            BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic |
                                 (isStatic ? BindingFlags.Static : BindingFlags.Instance);
            while (type != null)
            {
                MethodInfo method = type.GetMethod(name, flags, null, arguments, null);
                if (method != null)
                {
                    return method;
                }
                type = type.BaseType;
            }
            return null;
        }

        private static object ReadMember(object target, string name)
        {
            if (target == null)
            {
                return null;
            }
            System.Type type = target.GetType();
            BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance;
            while (type != null)
            {
                PropertyInfo property = type.GetProperty(name, flags);
                if (property != null)
                {
                    return property.GetValue(target, null);
                }
                FieldInfo field = type.GetField(name, flags);
                if (field != null)
                {
                    return field.GetValue(target);
                }
                type = type.BaseType;
            }
            return null;
        }

        private static object ReadStaticMember(System.Type type, string name)
        {
            BindingFlags flags = BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static;
            while (type != null)
            {
                PropertyInfo property = type.GetProperty(name, flags);
                if (property != null)
                {
                    return property.GetValue(null, null);
                }
                FieldInfo field = type.GetField(name, flags);
                if (field != null)
                {
                    return field.GetValue(null);
                }
                type = type.BaseType;
            }
            return null;
        }

        private static string ReadStringId(object target, string name)
        {
            object stringId = ReadMember(target, name);
            string value = ToText(ReadMember(stringId, "str"));
            return string.IsNullOrEmpty(value) ? ToText(stringId) : value;
        }

        private static int ToInt(object value)
        {
            try
            {
                return value == null ? 0 : Convert.ToInt32(value, CultureInfo.InvariantCulture);
            }
            catch
            {
                return 0;
            }
        }

        private static decimal ToDecimal(object value)
        {
            try
            {
                return value == null ? 0m : Convert.ToDecimal(value, CultureInfo.InvariantCulture);
            }
            catch
            {
                return 0m;
            }
        }

        private static string ToText(object value)
        {
            return value == null ? string.Empty : Convert.ToString(value, CultureInfo.InvariantCulture);
        }

        private static string DifficultyName(int difficulty)
        {
            switch (difficulty)
            {
                case 0: return "BASIC";
                case 1: return "ADVANCED";
                case 2: return "EXPERT";
                case 3: return "MASTER";
                case 4: return "Re:MASTER";
                default: return difficulty >= 0 ? "UTAGE" : string.Empty;
            }
        }
    }

    internal sealed class Snapshot
    {
        public int Player;
        public uint Track;
        public uint Critical;
        public uint Perfect;
        public uint Great;
        public uint Good;
        public uint Miss;
        public uint Combo;
        public uint DxScore;
        public decimal Achievement;
        public int MusicId;
        public int Difficulty = -1;
        public string Title = string.Empty;
        public string Artist = string.Empty;
        public string Chart = string.Empty;
        public string Level = string.Empty;
        public decimal Constant;
        public decimal Progress;

        public uint TotalJudgements
        {
            get { return Critical + Perfect + Great + Good + Miss; }
        }

        public bool SameValues(Snapshot other)
        {
            return other != null &&
                   Player == other.Player &&
                   Track == other.Track &&
                   Critical == other.Critical &&
                   Perfect == other.Perfect &&
                   Great == other.Great &&
                   Good == other.Good &&
                   Miss == other.Miss &&
                   Combo == other.Combo &&
                   DxScore == other.DxScore &&
                   MusicId == other.MusicId &&
                   Difficulty == other.Difficulty &&
                   Title == other.Title &&
                   Artist == other.Artist &&
                   Chart == other.Chart &&
                   Level == other.Level &&
                   Constant == other.Constant;
        }

        public string ToJson(string eventName, string status)
        {
            return string.Format(
                CultureInfo.InvariantCulture,
                "{{\"event\":\"{0}\",\"status\":\"{1}\",\"player\":{2},\"track\":{3}," +
                "\"critical\":{4},\"perfect\":{5},\"great\":{6},\"good\":{7},\"miss\":{8}," +
                "\"combo\":{9},\"dx_score\":{10},\"achievement\":{11:0.0000}," +
                "\"music_id\":{12},\"difficulty_id\":{13},\"title\":\"{14}\"," +
                "\"artist\":\"{15}\",\"chart\":\"{16}\",\"level\":\"{17}\"," +
                "\"constant\":{18:0.0},\"progress\":{19:0.0000}}}",
                eventName, status, Player, Track, Critical, Perfect, Great, Good, Miss,
                Combo, DxScore, Achievement, MusicId, Difficulty, JsonEscape(Title),
                JsonEscape(Artist), JsonEscape(Chart), JsonEscape(Level), Constant, Progress);
        }

        private static string JsonEscape(string value)
        {
            if (string.IsNullOrEmpty(value))
            {
                return string.Empty;
            }
            StringBuilder result = new StringBuilder(value.Length + 8);
            foreach (char character in value)
            {
                switch (character)
                {
                    case '\\': result.Append("\\\\"); break;
                    case '"': result.Append("\\\""); break;
                    case '\b': result.Append("\\b"); break;
                    case '\f': result.Append("\\f"); break;
                    case '\n': result.Append("\\n"); break;
                    case '\r': result.Append("\\r"); break;
                    case '\t': result.Append("\\t"); break;
                    default:
                        if (character < 32)
                        {
                            result.Append("\\u");
                            result.Append(((int)character).ToString("x4", CultureInfo.InvariantCulture));
                        }
                        else
                        {
                            result.Append(character);
                        }
                        break;
                }
            }
            return result.ToString();
        }
    }

    internal sealed class BridgeConfig
    {
        public bool Enabled = true;
        public int Port = 8891;
        public int PublishIntervalMs = 250;

        public static BridgeConfig Load(string path)
        {
            BridgeConfig config = new BridgeConfig();
            if (!File.Exists(path))
            {
                return config;
            }

            foreach (string raw in File.ReadAllLines(path))
            {
                string line = raw.Trim();
                if (line.Length == 0 || line.StartsWith("#") || line.StartsWith(";"))
                {
                    continue;
                }

                int separator = line.IndexOf('=');
                if (separator <= 0)
                {
                    continue;
                }

                string key = line.Substring(0, separator).Trim();
                string value = line.Substring(separator + 1).Trim();
                int number;

                if (key.Equals("Enabled", StringComparison.OrdinalIgnoreCase))
                {
                    bool enabled;
                    if (bool.TryParse(value, out enabled))
                    {
                        config.Enabled = enabled;
                    }
                }
                else if (key.Equals("Port", StringComparison.OrdinalIgnoreCase) &&
                         int.TryParse(value, out number) && number >= 1024 && number <= 65535)
                {
                    config.Port = number;
                }
                else if (key.Equals("PublishIntervalMs", StringComparison.OrdinalIgnoreCase) &&
                         int.TryParse(value, out number) && number >= 50 && number <= 5000)
                {
                    config.PublishIntervalMs = number;
                }
            }

            return config;
        }
    }

    internal sealed class SseServer
    {
        private sealed class ClientConnection
        {
            public TcpClient Client;
            public NetworkStream Stream;
        }

        private readonly int _port;
        private readonly object _clientsLock = new object();
        private readonly object _queueLock = new object();
        private readonly List<ClientConnection> _clients = new List<ClientConnection>();
        private readonly Queue<string> _queue = new Queue<string>();
        private readonly AutoResetEvent _wake = new AutoResetEvent(false);
        private readonly UTF8Encoding _utf8 = new UTF8Encoding(false);
        private volatile bool _running;
        private TcpListener _listener;
        private Thread _acceptThread;
        private Thread _sendThread;

        public SseServer(int port)
        {
            _port = port;
        }

        public bool IsRunning
        {
            get { return _running; }
        }

        public void Start()
        {
            if (_running)
            {
                return;
            }

            _listener = new TcpListener(IPAddress.Loopback, _port);
            _listener.Server.SetSocketOption(SocketOptionLevel.Socket, SocketOptionName.ReuseAddress, true);
            _listener.Start();
            _running = true;

            _acceptThread = new Thread(AcceptLoop);
            _acceptThread.IsBackground = true;
            _acceptThread.Name = "MaiDGBridge-Accept";
            _acceptThread.Start();

            _sendThread = new Thread(SendLoop);
            _sendThread.IsBackground = true;
            _sendThread.Name = "MaiDGBridge-Send";
            _sendThread.Start();
        }

        public void PublishJson(string json)
        {
            if (!_running || string.IsNullOrEmpty(json))
            {
                return;
            }

            lock (_queueLock)
            {
                while (_queue.Count >= 512)
                {
                    _queue.Dequeue();
                }
                _queue.Enqueue("data: " + json + "\n\n");
            }
            _wake.Set();
        }

        public void Stop()
        {
            if (!_running)
            {
                return;
            }

            _running = false;
            _wake.Set();

            try
            {
                _listener.Stop();
            }
            catch
            {
            }

            CloseAllClients();

            if (_acceptThread != null && _acceptThread.IsAlive)
            {
                _acceptThread.Join(1500);
            }
            if (_sendThread != null && _sendThread.IsAlive)
            {
                _sendThread.Join(1500);
            }
        }

        private void AcceptLoop()
        {
            while (_running)
            {
                try
                {
                    TcpClient client = _listener.AcceptTcpClient();
                    ThreadPool.QueueUserWorkItem(InitializeClient, client);
                }
                catch (SocketException)
                {
                    if (!_running)
                    {
                        return;
                    }
                }
                catch (ObjectDisposedException)
                {
                    return;
                }
            }
        }

        private void InitializeClient(object state)
        {
            TcpClient client = (TcpClient)state;
            try
            {
                client.NoDelay = true;
                client.ReceiveTimeout = 3000;
                client.SendTimeout = 1500;
                NetworkStream stream = client.GetStream();
                string request = ReadHeaders(stream, 8192);

                if (!request.StartsWith("GET /events ", StringComparison.Ordinal) &&
                    !request.StartsWith("GET /events?", StringComparison.Ordinal))
                {
                    byte[] notFound = Encoding.ASCII.GetBytes(
                        "HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
                    stream.Write(notFound, 0, notFound.Length);
                    client.Close();
                    return;
                }

                byte[] response = Encoding.ASCII.GetBytes(
                    "HTTP/1.1 200 OK\r\n" +
                    "Content-Type: text/event-stream; charset=utf-8\r\n" +
                    "Cache-Control: no-cache\r\n" +
                    "Connection: keep-alive\r\n" +
                    "Access-Control-Allow-Origin: *\r\n\r\n");
                stream.Write(response, 0, response.Length);
                byte[] connected = Encoding.ASCII.GetBytes(": connected\n\n");
                stream.Write(connected, 0, connected.Length);

                ClientConnection connection = new ClientConnection { Client = client, Stream = stream };
                lock (_clientsLock)
                {
                    if (!_running)
                    {
                        client.Close();
                        return;
                    }
                    _clients.Add(connection);
                }
            }
            catch
            {
                try
                {
                    client.Close();
                }
                catch
                {
                }
            }
        }

        private void SendLoop()
        {
            Stopwatch heartbeat = Stopwatch.StartNew();
            while (_running)
            {
                _wake.WaitOne(1000, false);
                List<string> frames = new List<string>();
                lock (_queueLock)
                {
                    while (_queue.Count > 0)
                    {
                        frames.Add(_queue.Dequeue());
                    }
                }

                if (heartbeat.ElapsedMilliseconds >= 5000)
                {
                    frames.Add(": heartbeat\n\n");
                    heartbeat.Reset();
                    heartbeat.Start();
                }

                foreach (string frame in frames)
                {
                    Broadcast(frame);
                }
            }
        }

        private void Broadcast(string frame)
        {
            byte[] data = _utf8.GetBytes(frame);
            ClientConnection[] clients;
            lock (_clientsLock)
            {
                clients = _clients.ToArray();
            }

            foreach (ClientConnection connection in clients)
            {
                try
                {
                    connection.Stream.Write(data, 0, data.Length);
                    connection.Stream.Flush();
                }
                catch
                {
                    RemoveClient(connection);
                }
            }
        }

        private void RemoveClient(ClientConnection connection)
        {
            lock (_clientsLock)
            {
                _clients.Remove(connection);
            }
            try
            {
                connection.Client.Close();
            }
            catch
            {
            }
        }

        private void CloseAllClients()
        {
            ClientConnection[] clients;
            lock (_clientsLock)
            {
                clients = _clients.ToArray();
                _clients.Clear();
            }
            foreach (ClientConnection connection in clients)
            {
                try
                {
                    connection.Client.Close();
                }
                catch
                {
                }
            }
        }

        private static string ReadHeaders(NetworkStream stream, int maxBytes)
        {
            MemoryStream buffer = new MemoryStream();
            int previous = -1;
            int beforePrevious = -1;
            int thirdPrevious = -1;

            while (buffer.Length < maxBytes)
            {
                int value = stream.ReadByte();
                if (value < 0)
                {
                    break;
                }
                buffer.WriteByte((byte)value);

                bool lfLf = previous == '\n' && value == '\n';
                bool crlfCrLf = thirdPrevious == '\r' && beforePrevious == '\n' &&
                                  previous == '\r' && value == '\n';
                if (lfLf || crlfCrLf)
                {
                    break;
                }

                thirdPrevious = beforePrevious;
                beforePrevious = previous;
                previous = value;
            }

            return Encoding.ASCII.GetString(buffer.ToArray());
        }
    }
}
