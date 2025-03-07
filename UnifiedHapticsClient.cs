using System;
using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using UnityEngine.Events;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

/// <summary>
/// Client for connecting to the Python bHaptics UDP API server.
/// Enables Unity to control bHaptics devices with automatic discovery and reconnection.
/// </summary>
/// <remarks>
/// Author: Pi Ko (pi.ko@nyu.edu)
/// Date: March 7, 2025
/// </remarks>
public class UnifiedHapticsClient : MonoBehaviour
{
    #region Inspector Fields

    [Header("Connection Settings")]
    [Tooltip("If true, will automatically try to discover the server on start")]
    [SerializeField] private bool autoConnectOnStart = true;

    [Tooltip("Port used for sending commands to the server (default: 9128)")]
    [SerializeField] private int serverPort = 9128;

    [Tooltip("Port used for discovery broadcasts (default: 9129)")]
    [SerializeField] private int discoveryPort = 9129;

    [Tooltip("How often to check connection status (seconds)")]
    [SerializeField] private float connectionCheckInterval = 5.0f;

    [Tooltip("How often to retry connection if disconnected (seconds)")]
    [SerializeField] private float reconnectInterval = 3.0f;

    [Header("Debug Settings")]
    [SerializeField] private bool logDebugMessages = true;
    [SerializeField] private bool logVerboseMessages = false;
    [SerializeField] private bool visualizeHapticFeedback = true;

    [Header("Events")]
    [SerializeField] private UnityEvent onConnected;
    [SerializeField] private UnityEvent onDisconnected;
    [SerializeField] private UnityEvent<string> onCommandResponse;
    [SerializeField] private UnityEvent<string> onError;
    [SerializeField] private UnityEvent<string> onStatusUpdate;

    #endregion

    #region Private Fields

    // UDP networking
    private UdpClient commandClient;
    private UdpClient discoveryClient;
    private IPEndPoint serverEndPoint;
    private string clientId;

    // Connection state
    private bool isConnected = false;
    private bool isConnecting = false;
    private bool hasInitialized = false;
    private string serverId;
    private float lastStatusTime;

    // Command tracking
    private Dictionary<string, CommandInfo> pendingCommands = new Dictionary<string, CommandInfo>();
    private int commandCounter = 0;

    // Threading
    private CancellationTokenSource receiveCts;
    private Task receiveTask;

    // Locks for thread safety
    private object commandLock = new object();
    private object stateLock = new object();

    // Event handlers
    private Dictionary<string, Action<JObject>> eventHandlers = new Dictionary<string, Action<JObject>>();

    #endregion

    #region Properties

    /// <summary>
    /// Gets a value indicating whether the client is connected to the server.
    /// </summary>
    public bool IsConnected
    {
        get
        {
            lock (stateLock)
            {
                return isConnected;
            }
        }
        private set
        {
            bool wasConnected;
            lock (stateLock)
            {
                wasConnected = isConnected;
                isConnected = value;
            }

            // Fire events if state changed
            if (wasConnected && !value)
            {
                onDisconnected?.Invoke();
            }
            else if (!wasConnected && value)
            {
                onConnected?.Invoke();
            }
        }
    }

    /// <summary>
    /// Gets the server ID if connected, otherwise returns "Not connected".
    /// </summary>
    public string ServerId
    {
        get
        {
            lock (stateLock)
            {
                return IsConnected ? serverId : "Not connected";
            }
        }
    }

    /// <summary>
    /// Gets a value indicating whether the client is currently in the process of connecting.
    /// </summary>
    public bool IsConnecting
    {
        get
        {
            lock (stateLock)
            {
                return isConnecting;
            }
        }
        private set
        {
            lock (stateLock)
            {
                isConnecting = value;
            }
        }
    }

    #endregion

    #region Unity Lifecycle Methods

    private void Awake()
    {
        // Generate a unique client ID
        clientId = SystemInfo.deviceUniqueIdentifier + "-" + Guid.NewGuid().ToString();
        LogInfo($"Client ID: {clientId}");
    }

    private void Start()
    {
        if (autoConnectOnStart)
        {
            ConnectToServer();
        }
    }

    private void OnEnable()
    {
        if (hasInitialized && !IsConnected && !IsConnecting)
        {
            ConnectToServer();
        }
    }

    private void OnDisable()
    {
        Disconnect();
    }

    private void OnDestroy()
    {
        Disconnect();
    }

    private void OnApplicationQuit()
    {
        Disconnect();
    }

    private void Update()
    {
        // Check if we need to ping the server for status
        if (IsConnected && Time.time - lastStatusTime > connectionCheckInterval)
        {
            lastStatusTime = Time.time;
            SendCommand("ping", new Dictionary<string, object> { { "message", "status_check" } }, null);
        }
    }

    #endregion

    #region Connection Methods

    /// <summary>
    /// Initiates connection to the haptics server, first trying discovery.
    /// </summary>
    public void ConnectToServer()
    {
        if (IsConnecting || IsConnected)
            return;

        IsConnecting = true;
        hasInitialized = true;

        LogInfo("Connecting to haptics server...");

        // Start with discovery
        StartCoroutine(DiscoverServer());
    }

    /// <summary>
    /// Directly connect to a server at the specified IP address.
    /// </summary>
    /// <param name="ipAddress">The IP address of the server.</param>
    public void ConnectToServerDirectly(string ipAddress)
    {
        if (IsConnecting || IsConnected)
            return;

        IsConnecting = true;
        LogInfo($"Connecting directly to server at {ipAddress}:{serverPort}");
        
        try
        {
            // Initialize the command client
            InitializeCommandClient();
            
            // Set up the server endpoint
            serverEndPoint = new IPEndPoint(IPAddress.Parse(ipAddress), serverPort);
            
            // Start receiving responses
            StartReceiving();
            
            // Send a ping to check connection
            SendCommand("ping", new Dictionary<string, object> { { "message", "connection_check" } }, OnConnectionPingResponse);
        }
        catch (Exception ex)
        {
            LogError($"Failed to connect to server: {ex.Message}");
            IsConnecting = false;
        }
    }
    
    /// <summary>
    /// Disconnects from the haptics server.
    /// </summary>
    public void Disconnect()
    {
        if (!hasInitialized)
            return;
            
        LogInfo("Disconnecting from haptics server");
        
        // Stop receiving
        StopReceiving();
        
        // Clean up clients
        if (commandClient != null)
        {
            commandClient.Close();
            commandClient = null;
        }
        
        if (discoveryClient != null)
        {
            discoveryClient.Close();
            discoveryClient = null;
        }
        
        // Update state
        IsConnected = false;
        IsConnecting = false;
        serverEndPoint = null;
    }
    
    /// <summary>
    /// Initiates the discovery process to find the haptics server on the network.
    /// </summary>
    private IEnumerator DiscoverServer()
    {
        LogInfo("Starting server discovery");
        
        try
        {
            // Create a discovery client
            discoveryClient = new UdpClient();
            discoveryClient.EnableBroadcast = true;
            
            // Send broadcast discovery message
            byte[] discoveryMsg = Encoding.UTF8.GetBytes("UNITY_HAPTICS_DISCOVERY_REQUEST");
            
            // Try all available broadcast addresses
            string[] broadcastAddresses = { "255.255.255.255", "192.168.1.255", "192.168.0.255", "10.0.0.255", "10.0.1.255" };
            
            int attempts = 0;
            bool serverFound = false;
            
            // Listen for responses asynchronously
            Task<UdpReceiveResult> receiveTask = null;
            
            while (!serverFound && attempts < 5 && !IsConnected)
            {
                attempts++;
                LogDebug($"Discovery attempt {attempts}...");
                
                foreach (string address in broadcastAddresses)
                {
                    try
                    {
                        // Send discovery packet
                        IPEndPoint broadcastEndPoint = new IPEndPoint(IPAddress.Parse(address), discoveryPort);
                        discoveryClient.Send(discoveryMsg, discoveryMsg.Length, broadcastEndPoint);
                        LogVerbose($"Sent discovery broadcast to {address}:{discoveryPort}");
                    }
                    catch (Exception ex)
                    {
                        LogVerbose($"Failed to send to {address}: {ex.Message}");
                    }
                }
                
                // Start receiving if we haven't already
                if (receiveTask == null || receiveTask.IsCompleted)
                {
                    receiveTask = discoveryClient.ReceiveAsync();
                }
                
                // Wait up to 1 second for a response (non-blocking)
                float startTime = Time.time;
                while (Time.time - startTime < 1.0f)
                {
                    if (receiveTask.IsCompleted)
                    {
                        try
                        {
                            UdpReceiveResult result = receiveTask.Result;
                            
                            // Process the discovery response
                            string response = Encoding.UTF8.GetString(result.Buffer);
                            LogVerbose($"Received: {response} from {result.RemoteEndPoint}");
                            
                            try
                            {
                                JObject jsonResponse = JObject.Parse(response);
                                string responseType = jsonResponse["type"]?.ToString();
                                
                                if (responseType == "UNITY_HAPTICS_SERVER")
                                {
                                    // Found the server!
                                    serverId = jsonResponse["server_id"]?.ToString();
                                    int apiPort = jsonResponse["api_port"] != null ? 
                                        int.Parse(jsonResponse["api_port"].ToString()) : serverPort;
                                    
                                    LogInfo($"Found haptics server: ID={serverId}, IP={result.RemoteEndPoint.Address}, Port={apiPort}");
                                    
                                    // Connect to the discovered server
                                    serverEndPoint = new IPEndPoint(result.RemoteEndPoint.Address, apiPort);
                                    InitializeCommandClient();
                                    StartReceiving();
                                    
                                    // Send a ping to verify connection
                                    SendCommand("ping", new Dictionary<string, object> { { "message", "discovery_connection" } }, OnConnectionPingResponse);
                                    
                                    serverFound = true;
                                    break;
                                }
                            }
                            catch (JsonException)
                            {
                                LogVerbose("Received non-JSON response during discovery");
                            }
                            
                            // Start a new receive task
                            receiveTask = discoveryClient.ReceiveAsync();
                        }
                        catch (Exception ex)
                        {
                            LogVerbose($"Error receiving discovery response: {ex.Message}");
                            receiveTask = discoveryClient.ReceiveAsync(); // Try again
                        }
                    }
                    
                    yield return null; // Wait a frame before checking again
                }
                
                yield return new WaitForSeconds(0.5f);
            }
            
            if (!serverFound)
            {
                LogWarning("No haptics server found through discovery.");
                IsConnecting = false;
                
                // Try again after delay if not connected
                if (!IsConnected)
                {
                    LogInfo($"Will retry connecting in {reconnectInterval} seconds.");
                    StartCoroutine(RetryConnect());
                }
            }
        }
        catch (Exception ex)
        {
            LogError($"Error during server discovery: {ex.Message}");
            IsConnecting = false;
            
            // Try again after delay
            StartCoroutine(RetryConnect());
        }
        finally
        {
            // Clean up discovery client if we have a command client
            if (serverFound && discoveryClient != null)
            {
                discoveryClient.Close();
                discoveryClient = null;
            }
        }
    }
    
    /// <summary>
    /// Retry connecting after a delay.
    /// </summary>
    private IEnumerator RetryConnect()
    {
        yield return new WaitForSeconds(reconnectInterval);
        
        if (!IsConnected && !IsConnecting)
        {
            ConnectToServer();
        }
    }
    
    /// <summary>
    /// Initializes the command client for sending commands to the server.
    /// </summary>
    private void InitializeCommandClient()
    {
        if (commandClient != null)
        {
            commandClient.Close();
        }
        
        commandClient = new UdpClient();
    }
    
    /// <summary>
    /// Starts the background task for receiving responses from the server.
    /// </summary>
    private void StartReceiving()
    {
        // Cancel any existing receive task
        StopReceiving();
        
        // Start a new receive task
        receiveCts = new CancellationTokenSource();
        receiveTask = ReceiveResponsesAsync(receiveCts.Token);
    }
    
    /// <summary>
    /// Stops the background task for receiving responses.
    /// </summary>
    private void StopReceiving()
    {
        if (receiveCts != null)
        {
            receiveCts.Cancel();
            receiveCts = null;
        }
        
        receiveTask = null;
    }
    
    /// <summary>
    /// Background task that continuously receives and processes responses from the server.
    /// </summary>
    private async Task ReceiveResponsesAsync(CancellationToken cancellationToken)
    {
        try
        {
            LogDebug("Starting to receive responses");
            
            // Create a local endpoint to listen on
            IPEndPoint localEP = new IPEndPoint(IPAddress.Any, 0);
            
            while (!cancellationToken.IsCancellationRequested)
            {
                try
                {
                    UdpReceiveResult result = await commandClient.ReceiveAsync();
                    string response = Encoding.UTF8.GetString(result.Buffer);
                    
                    // Process the response on the main thread
                    UnityMainThreadDispatcher.Instance().Enqueue(() => 
                    {
                        ProcessResponse(response);
                    });
                }
                catch (SocketException ex)
                {
                    if (cancellationToken.IsCancellationRequested)
                        break;
                        
                    LogError($"Socket error while receiving: {ex.Message}");
                    
                    // If we get a fatal socket error, mark as disconnected
                    if (ex.SocketErrorCode == SocketError.ConnectionReset ||
                        ex.SocketErrorCode == SocketError.NetworkDown ||
                        ex.SocketErrorCode == SocketError.NetworkUnreachable)
                    {
                        IsConnected = false;
                        break;
                    }
                }
                catch (Exception ex)
                {
                    if (cancellationToken.IsCancellationRequested)
                        break;
                        
                    LogError($"Error receiving response: {ex.Message}");
                    await Task.Delay(100, cancellationToken); // Small delay to avoid tight loop
                }
            }
        }
        catch (TaskCanceledException)
        {
            // Expected when cancelling
            LogVerbose("Response receiver cancelled");
        }
        catch (Exception ex)
        {
            LogError($"Fatal error in receive task: {ex.Message}");
        }
        
        LogDebug("Stopped receiving responses");
    }
    
    /// <summary>
    /// Process a response received from the server.
    /// </summary>
    /// <param name="response">The JSON response string.</param>
    private void ProcessResponse(string response)
    {
        try
        {
            JObject jsonResponse = JObject.Parse(response);
            string responseType = jsonResponse["type"]?.ToString();
            
            // Handle different response types
            switch (responseType)
            {
                case "response":
                    ProcessCommandResponse(jsonResponse);
                    break;
                    
                case "error":
                    ProcessErrorResponse(jsonResponse);
                    break;
                    
                case "status_update":
                    ProcessStatusUpdate(jsonResponse);
                    break;
                    
                case "event":
                    ProcessEventNotification(jsonResponse);
                    break;
                    
                default:
                    LogWarning($"Unknown response type: {responseType}");
                    break;
            }
        }
        catch (JsonException ex)
        {
            LogError($"Error parsing response: {ex.Message}\nResponse: {response}");
        }
        catch (Exception ex)
        {
            LogError($"Error processing response: {ex.Message}");
        }
    }
    
    /// <summary>
    /// Process a successful command response.
    /// </summary>
    private void ProcessCommandResponse(JObject response)
    {
        string commandId = response["command_id"]?.ToString();
        JObject result = response["result"] as JObject;
        
        if (string.IsNullOrEmpty(commandId))
        {
            LogWarning("Received response without command ID");
            return;
        }
        
        // Look up the pending command
        CommandInfo commandInfo = null;
        lock (commandLock)
        {
            if (pendingCommands.TryGetValue(commandId, out commandInfo))
            {
                pendingCommands.Remove(commandId);
            }
        }
        
        // If we found the command, execute its callback
        if (commandInfo != null)
        {
            if (commandInfo.Callback != null)
            {
                try
                {
                    commandInfo.Callback(result);
                }
                catch (Exception ex)
                {
                    LogError($"Error in response callback: {ex.Message}");
                }
            }
            
            // Always fire the general event
            onCommandResponse?.Invoke(result?.ToString(Formatting.None) ?? "{}");
        }
        else
        {
            LogWarning($"Received response for unknown command ID: {commandId}");
        }
    }
    
    /// <summary>
    /// Process an error response.
    /// </summary>
    private void ProcessErrorResponse(JObject response)
    {
        string commandId = response["command_id"]?.ToString();
        string error = response["error"]?.ToString();
        
        LogError($"Server error: {error}");
        
        // Look up the pending command
        if (!string.IsNullOrEmpty(commandId))
        {
            CommandInfo commandInfo = null;
            lock (commandLock)
            {
                if (pendingCommands.TryGetValue(commandId, out commandInfo))
                {
                    pendingCommands.Remove(commandId);
                }
            }
            
            // If we found the command, execute its callback with an error result
            if (commandInfo != null && commandInfo.Callback != null)
            {
                try
                {
                    JObject errorResult = new JObject
                    {
                        ["success"] = false,
                        ["error"] = error
                    };
                    
                    commandInfo.Callback(errorResult);
                }
                catch (Exception ex)
                {
                    LogError($"Error in error callback: {ex.Message}");
                }
            }
        }
        
        // Fire the general error event
        onError?.Invoke(error ?? "Unknown error");
    }
    
    /// <summary>
    /// Process a status update from the server.
    /// </summary>
    private void ProcessStatusUpdate(JObject response)
    {
        JObject status = response["status"] as JObject;
        
        if (status != null)
        {
            // Update server ID
            serverId = status["server_id"]?.ToString() ?? serverId;
            
            // Fire the status update event
            onStatusUpdate?.Invoke(status.ToString(Formatting.None));
            
            // Reset the status timer
            lastStatusTime = Time.time;
        }
    }
    
    /// <summary>
    /// Process an event notification from the server.
    /// </summary>
    private void ProcessEventNotification(JObject response)
    {
        string eventType = response["event_type"]?.ToString();
        JObject data = response["data"] as JObject;
        
        if (!string.IsNullOrEmpty(eventType) && data != null)
        {
            // Check if we have a handler for this event type
            if (eventHandlers.TryGetValue(eventType, out Action<JObject> handler))
            {
                try
                {
                    handler(data);
                }
                catch (Exception ex)
                {
                    LogError($"Error in event handler for {eventType}: {ex.Message}");
                }
            }
        }
    }
    
    /// <summary>
    /// Callback when receiving a response to the connection ping.
    /// </summary>
    private void OnConnectionPingResponse(JObject response)
    {
        bool success = response["success"]?.ToObject<bool>() ?? false;
        
        if (success)
        {
            LogInfo("Successfully connected to haptics server");
            IsConnected = true;
            IsConnecting = false;
            lastStatusTime = Time.time;
            
            // Get the server status
            SendCommand("get_status", null, OnStatusResponse);
        }
        else
        {
            LogWarning("Failed to connect to haptics server");
            IsConnected = false;
            IsConnecting = false;
            
            // Try again after delay
            StartCoroutine(RetryConnect());
        }
    }
    
    /// <summary>
    /// Callback when receiving a response to the status request.
    /// </summary>
    private void OnStatusResponse(JObject response)
    {
        // Updated details will be handled in the status handler
        LogDebug("Received server status");
    }

    #endregion
    
    #region Command Methods
    
    /// <summary>
    /// Sends a command to the haptics server.
    /// </summary>
    /// <param name="command">The command name.</param>
    /// <param name="parameters">The command parameters.</param>
    /// <param name="callback">Optional callback to handle the response.</param>
    /// <returns>The command ID for tracking.</returns>
    public string SendCommand(string command, Dictionary<string, object> parameters, Action<JObject> callback)
    {
        if (serverEndPoint == null)
        {
            LogWarning("Cannot send command: Server not connected");
            return null;
        }
        
        try
        {
            // Generate command ID
            string commandId = $"{clientId}:{commandCounter++}";
            
            // Create command JSON
            JObject commandJson = new JObject
            {
                ["command"] = command,
                ["command_id"] = commandId,
                ["client_id"] = clientId,
                ["timestamp"] = DateTime.UtcNow.ToString("o")
            };
            
            // Add parameters if provided
            if (parameters != null && parameters.Count > 0)
            {
                JObject paramsJson = new JObject();
                foreach (var kvp in parameters)
                {
                    paramsJson[kvp.Key] = kvp.Value != null ? 
                        JToken.FromObject(kvp.Value) : 
                        JValue.CreateNull();
                }
                
                commandJson["params"] = paramsJson;
            }
            
            // Track the command
            lock (commandLock)
            {
                pendingCommands[commandId] = new CommandInfo
                {
                    Command = command,
                    Timestamp = DateTime.UtcNow,
                    Callback = callback
                };
            }
            
            // Send the command
            string jsonString = commandJson.ToString(Formatting.None);
            byte[] bytes = Encoding.UTF8.GetBytes(jsonString);
            
            commandClient.Send(bytes, bytes.Length, serverEndPoint);
            
            LogVerbose($"Sent command: {command} (ID: {commandId})");
            return commandId;
        }
        catch (Exception ex)
        {
            LogError($"Error sending command {command}: {ex.Message}");
            return null;
        }
    }
    
    /// <summary>
    /// Registers an event handler for the specified event type.
    /// </summary>
    /// <param name="eventType">The event type.</param>
    /// <param name="handler">The handler function.</param>
    public void RegisterEventHandler(string eventType, Action<JObject> handler)
    {
        if (!string.IsNullOrEmpty(eventType) && handler != null)
        {
            eventHandlers[eventType] = handler;
            
            // Register with the server if connected
            if (IsConnected)
            {
                Dictionary<string, object> parameters = new Dictionary<string, object>
                {
                    { "event_type", eventType }
                };
                
                SendCommand("register_event_callback", parameters, null);
            }
        }
    }
    
    /// <summary>
    /// Unregisters an event handler for the specified event type.
    /// </summary>
    /// <param name="eventType">The event type.</param>
    public void UnregisterEventHandler(string eventType)
    {
        if (!string.IsNullOrEmpty(eventType))
        {
            eventHandlers.Remove(eventType);
            
            // Unregister with the server if connected
            if (IsConnected)
            {
                Dictionary<string, object> parameters = new Dictionary<string, object>
                {
                    { "event_type", eventType }
                };
                
                SendCommand("unregister_event_callback", parameters, null);
            }
        }
    }
    
    #endregion
    
    #region Haptics Control Methods
    
    /// <summary>
    /// Activates a specific motor on the vest.
    /// </summary>
    /// <param name="panel">The panel ('front' or 'back').</param>
    /// <param name="motorIndex">The motor index (0-19).</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="durationMs">The duration in milliseconds.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string ActivateDiscreteMotor(string panel, int motorIndex, int intensity, int durationMs, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = new Dictionary<string, object>
        {
            { "panel", panel },
            { "motor_index", motorIndex },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] {panel} motor {motorIndex} at {intensity}% for {durationMs}ms");
        }
        
        return SendCommand("activate_discrete", parameters, callback);
    }
    
    /// <summary>
    /// Activates motors on the vest using funnelling effect.
    /// </summary>
    /// <param name="panel">The panel ('front' or 'back').</param>
    /// <param name="x">The X coordinate (0.0-1.0).</param>
    /// <param name="y">The Y coordinate (0.0-1.0).</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="durationMs">The duration in milliseconds.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string ActivateFunnelling(string panel, float x, float y, int intensity, int durationMs, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = new Dictionary<string, object>
        {
            { "panel", panel },
            { "x", x },
            { "y", y },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] {panel} funnelling at ({x:F2}, {y:F2}) at {intensity}% for {durationMs}ms");
        }
        
        return SendCommand("activate_funnelling", parameters, callback);
    }
    
    /// <summary>
    /// Activates a motor on the specified glove.
    /// </summary>
    /// <param name="glove">The glove ('left' or 'right').</param>
    /// <param name="motorIndex">The motor index (0-5).</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="durationMs">The duration in milliseconds.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string ActivateGloveMotor(string glove, int motorIndex, int intensity, int durationMs, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = new Dictionary<string, object>
        {
            { "glove", glove },
            { "motor_index", motorIndex },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] {glove} glove motor {motorIndex} at {intensity}% for {durationMs}ms");
        }
        
        return SendCommand("activate_glove_motor", parameters, callback);
    }
    
    /// <summary>
    /// Plays the predefined wave pattern.
    /// </summary>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string PlayWavePattern(Action<JObject> callback = null)
    {
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log("[HAPTIC] Playing wave pattern");
        }
        
        return SendCommand("play_wave_pattern", null, callback);
    }
    
    /// <summary>
    /// Plays the predefined alternating pattern.
    /// </summary>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string PlayAlternatingPattern(Action<JObject> callback = null)
    {
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log("[HAPTIC] Playing alternating pattern");
        }
        
        return SendCommand("play_alternating_pattern", null, callback);
    }
    
    /// <summary>
    /// Plays a custom pattern defined as a list of steps.
    /// </summary>
    /// <param name="pattern">The pattern steps.</param>
    /// <param name="durationMs">The duration for each step.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string PlayCustomPattern(object pattern, int durationMs, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = new Dictionary<string, object>
        {
            { "pattern", pattern },
            { "duration_ms", durationMs }
        };
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] Playing custom pattern with {durationMs}ms steps");
        }
        
        return SendCommand("play_custom_pattern", parameters, callback);
    }
    
    /// <summary>
    /// Plays a pattern from a tact file.
    /// </summary>
    /// <param name="patternFile">The path to the tact file.</param>
    /// <param name="key">Optional key to register the pattern under.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string PlayPattern(string patternFile, string key = null, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = new Dictionary<string, object>
        {
            { "pattern_file", patternFile }
        };
        
        if (!string.IsNullOrEmpty(key))
        {
            parameters["key"] = key;
        }
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] Playing pattern from file: {patternFile}");
        }
        
        return SendCommand("play_pattern", parameters, callback);
    }
    
    /// <summary>
    /// Stops the playback of patterns.
    /// </summary>
    /// <param name="key">Optional key of the pattern to stop.</param>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string StopPattern(string key = null, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = null;
        
        if (!string.IsNullOrEmpty(key))
        {
            parameters = new Dictionary<string, object>
            {
                { "key", key }
            };
        }
        
        // Visualize in editor
        if (visualizeHapticFeedback)
        {
            Debug.Log($"[HAPTIC] Stopping pattern{(key != null ? $": {key}" : "s")}");
        }
        
        return SendCommand("stop_pattern", parameters, callback);
    }
    
    /// <summary>
    /// Checks if a pattern is currently playing.
    /// </summary>
    /// <param name="key">Optional key of the pattern to check.</param>
    /// <param name="callback">Callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string IsPatternPlaying(string key = null, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = null;
        
        if (!string.IsNullOrEmpty(key))
        {
            parameters = new Dictionary<string, object>
            {
                { "key", key }
            };
        }
        
        return SendCommand("is_pattern_playing", parameters, callback);
    }
    
    /// <summary>
    /// Gets the status of the haptics devices.
    /// </summary>
    /// <param name="deviceType">Optional device type to check.</param>
    /// <param name="callback">Callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string GetDeviceStatus(string deviceType = null, Action<JObject> callback = null)
    {
        Dictionary<string, object> parameters = null;
        
        if (!string.IsNullOrEmpty(deviceType))
        {
            parameters = new Dictionary<string, object>
            {
                { "device_type", deviceType }
            };
        }
        
        return SendCommand("get_device_status", parameters, callback);
    }
    
    /// <summary>
    /// Shuts down the haptics server.
    /// </summary>
    /// <param name="callback">Optional callback for the response.</param>
    /// <returns>The command ID.</returns>
    public string ShutdownServer(Action<JObject> callback = null)
    {
        LogWarning("Shutting down haptics server");
        
        return SendCommand("shutdown", null, callback);
    }
    
    #endregion
    
    #region Logging Methods
    
    private void LogInfo(string message)
    {
        if (logDebugMessages)
        {
            Debug.Log($"[HapticsClient] {message}");
        }
    }
    
    private void LogDebug(string message)
    {
        if (logDebugMessages)
        {
            Debug.Log($"[HapticsClient] {message}");
        }
    }
    
    private void LogVerbose(string message)
    {
        if (logVerboseMessages)
        {
            Debug.Log($"[HapticsClient|Verbose] {message}");
        }
    }
    
    private void LogWarning(string message)
    {
        Debug.LogWarning($"[HapticsClient] {message}");
    }
    
    private void LogError(string message)
    {
        Debug.LogError($"[HapticsClient] {message}");
        onError?.Invoke(message);
    }
    
    #endregion
    
    #region Helper Classes
    
    /// <summary>
    /// Stores information about a pending command.
    /// </summary>
    private class CommandInfo
    {
        public string Command { get; set; }
        public DateTime Timestamp { get; set; }
        public Action<JObject> Callback { get; set; }
    }
    
    #endregion
}

/// <summary>
/// Helper class to dispatch actions to the Unity main thread.
/// Uses singleton pattern for easy access from any thread.
/// </summary>
public class UnityMainThreadDispatcher : MonoBehaviour
{
    private static UnityMainThreadDispatcher _instance;
    private readonly Queue<Action> _executionQueue = new Queue<Action>();
    private readonly object _lock = new object();

    /// <summary>
    /// Gets the instance of the dispatcher, creating it if needed.
    /// </summary>
    public static UnityMainThreadDispatcher Instance()
    {
        if (_instance == null)
        {
            var go = new GameObject("UnityMainThreadDispatcher");
            _instance = go.AddComponent<UnityMainThreadDispatcher>();
            DontDestroyOnLoad(go);
        }
        return _instance;
    }

    private void Awake()
    {
        if (_instance == null)
        {
            _instance = this;
            DontDestroyOnLoad(gameObject);
        }
    }

    private void Update()
    {
        lock (_lock)
        {
            while (_executionQueue.Count > 0)
            {
                _executionQueue.Dequeue().Invoke();
            }
        }
    }

    /// <summary>
    /// Enqueues an action to be executed on the main thread.
    /// </summary>
    /// <param name="action">The action to execute.</param>
    public void Enqueue(Action action)
    {
        lock (_lock)
        {
            _executionQueue.Enqueue(action);
        }
    }
}