using System;
using System.Collections;
using System.Collections.Generic;
using System.Net;
using System.Net.Sockets;
using System.Text;
using System.Threading;
using UnityEngine;
using UnityEngine.Events;

/// <summary>
/// HapticsManager interfaces with the Python haptics bridge to control bHaptics devices.
/// This script provides an easy-to-use API for triggering various haptic effects in Unity.
/// 
/// Features:
/// - UDP communication with the Python bridge script
/// - Automatic connection and handshake
/// - Easy-to-use methods for different haptic effects
/// - Example patterns for common haptic experiences
/// - Threaded message handling for responsive gameplay
/// 
/// Author: Pi Ko (pi.ko@nyu.edu)
/// Date: March 2024
/// </summary>
public class HapticsManager : MonoBehaviour
{
    #region Inspector Properties

    [Header("Connection Settings")]
    [Tooltip("IP address of the Python UDP server")]
    [SerializeField] private string serverIp = "127.0.0.1";
    
    [Tooltip("Port number of the Python UDP server")]
    [SerializeField] private int serverPort = 9930;
    
    [Tooltip("Timeout for response from server (milliseconds)")]
    [SerializeField] private int responseTimeout = 5000;
    
    [Tooltip("Whether to connect automatically on start")]
    [SerializeField] private bool autoConnect = true;

    [Header("Debug Settings")]
    [Tooltip("Enable verbose logging")]
    [SerializeField] private bool debugMode = true;
    
    [Tooltip("Log haptic events to console")]
    [SerializeField] private bool logHapticEvents = true;

    [Header("Events")]
    [Tooltip("Event triggered when connection is established")]
    public UnityEvent onConnected;
    
    [Tooltip("Event triggered when connection is lost")]
    public UnityEvent onDisconnected;
    
    [Tooltip("Event triggered when a haptic effect is played")]
    public UnityEvent onHapticEffectPlayed;

    #endregion

    #region Private Fields

    // UDP client for sending commands to the Python server
    private UdpClient udpClient;
    
    // Server endpoint
    private IPEndPoint serverEndPoint;
    
    // Flag indicating if connection is established
    private bool isConnected = false;
    
    // Queue for incoming messages
    private Queue<string> messageQueue = new Queue<string>();
    
    // Lock object for thread safety
    private object messageLock = new object();
    
    // Thread for receiving messages
    private Thread receiveThread;
    
    // Flag for controlling the receive thread
    private bool isReceiving = true;
    
    // Time of last heartbeat
    private float lastHeartbeatTime = 0f;
    
    // Heartbeat interval in seconds
    private float heartbeatInterval = 10f;

    #endregion

    #region Unity Lifecycle Methods

    /// <summary>
    /// Initialize the UDP client.
    /// </summary>
    private void Awake()
    {
        InitializeUdpClient();
    }

    /// <summary>
    /// Connect to the Python server on start if autoConnect is enabled.
    /// </summary>
    private void Start()
    {
        if (autoConnect)
        {
            ConnectToServer();
        }
    }

    /// <summary>
    /// Update is called once per frame. Process messages and send heartbeats.
    /// </summary>
    private void Update()
    {
        ProcessMessages();
        
        // Send heartbeat periodically if connected
        if (isConnected && Time.time - lastHeartbeatTime > heartbeatInterval)
        {
            SendHeartbeat();
            lastHeartbeatTime = Time.time;
        }
    }

    /// <summary>
    /// Clean up resources when the GameObject is destroyed.
    /// </summary>
    private void OnDestroy()
    {
        CleanUp();
    }

    /// <summary>
    /// Clean up resources when the application quits.
    /// </summary>
    private void OnApplicationQuit()
    {
        CleanUp();
    }

    #endregion

    #region Connection Management

    /// <summary>
    /// Initialize the UDP client.
    /// </summary>
    private void InitializeUdpClient()
{
    try
    {
        // Create the UDP client with a specific local port
        udpClient = new UdpClient(0);  // Use 0 to let the system assign an available port
        
        // Set up the server endpoint
        serverEndPoint = new IPEndPoint(IPAddress.Parse(serverIp), serverPort);
        
        // Configure the client
        udpClient.Client.ReceiveTimeout = responseTimeout;
        
        // Log the local port we're using
        IPEndPoint localEndPoint = (IPEndPoint)udpClient.Client.LocalEndPoint;
        LogMessage($"UDP client initialized on local port {localEndPoint.Port}");
    }
    catch (Exception e)
    {
        LogError($"Error initializing UDP client: {e.Message}");
    }
}

// Test the connection with a simple command

    /// <summary>
    /// Connect to the Python server by sending a handshake.
    /// </summary>
    public void ConnectToServer()
    {
        if (isConnected)
        {
            LogMessage("Already connected to server");
            return;
        }
        
        try
        {
            // Start the receive thread
            StartReceiveThread();
            
            // Send handshake to the server
            Dictionary<string, object> handshakeData = new Dictionary<string, object>
            {
                { "command", "handshake" },
                { "client_info", new Dictionary<string, string> {
                    { "application", Application.productName },
                    { "version", Application.version },
                    { "platform", Application.platform.ToString() }
                }}
            };
            
            // Send the handshake
            SendCommand(handshakeData);
            
            LogMessage("Handshake sent to server");
        }
        catch (Exception e)
        {
            LogError($"Error connecting to server: {e.Message}");
        }
    }

    /// <summary>
    /// Disconnect from the Python server.
    /// </summary>
    public void DisconnectFromServer()
    {
        if (!isConnected)
        {
            LogMessage("Not connected to server");
            return;
        }
        
        try
        {
            // Set isConnected to false
            isConnected = false;
            
            // Invoke disconnect event
            onDisconnected?.Invoke();
            
            LogMessage("Disconnected from server");
        }
        catch (Exception e)
        {
            LogError($"Error disconnecting from server: {e.Message}");
        }
    }

    /// <summary>
    /// Send a heartbeat to the server to keep the connection alive.
    /// </summary>
    private void SendHeartbeat()
    {
        if (!isConnected)
            return;
            
        Dictionary<string, object> heartbeatData = new Dictionary<string, object>
        {
            { "command", "heartbeat" }
        };
        
        SendCommand(heartbeatData);
        LogMessage("Heartbeat sent", isVerboseLog: true);
    }

    /// <summary>
    /// Start a thread to receive messages from the server.
    /// </summary>
    private void StartReceiveThread()
    {
        isReceiving = true;
        receiveThread = new Thread(new ThreadStart(ReceiveData));
        receiveThread.IsBackground = true;
        receiveThread.Start();
        LogMessage("Receive thread started");
    }

    /// <summary>
    /// Receive data from the server in a separate thread.
    /// </summary>
    private void ReceiveData()
{
    while (isReceiving)
    {
        try
        {
            IPEndPoint remoteEndPoint = new IPEndPoint(IPAddress.Any, 0);
            byte[] data = udpClient.Receive(ref remoteEndPoint);
            string message = Encoding.UTF8.GetString(data);
            
            // Log raw response for debugging
            Debug.Log($"Received raw response: {message}");
            
            // Add message to queue for processing in the main thread
            lock (messageLock)
            {
                messageQueue.Enqueue(message);
            }
        }
        catch (SocketException ex)
        {
            if (ex.SocketErrorCode != SocketError.TimedOut)
            {
                Debug.LogError($"Socket error: {ex.Message} (Error code: {ex.SocketErrorCode})");
            }
        }
        catch (Exception e)
        {
            if (isReceiving) // Only log if we're still supposed to be receiving
            {
                Debug.LogError($"Error receiving data: {e.Message}");
            }
        }
        
        // Small delay to prevent high CPU usage
        Thread.Sleep(10);
    }
}

    /// <summary>
    /// Process messages received from the server.
    /// </summary>
    private void ProcessMessages()
    {
        if (messageQueue.Count == 0)
            return;

        string message;
        lock (messageLock)
        {
            message = messageQueue.Dequeue();
        }

        try
        {
            // Parse the JSON response
#if UNITY_2018_1_OR_NEWER
            // Unity 2018.1+ includes JsonUtility which can parse directly
            ServerResponse response = JsonUtility.FromJson<ServerResponse>(message);
#else
            // For older Unity versions, use a simpler approach
            ServerResponse response = ParseResponse(message);
#endif
            
            // Process based on status
            switch (response.status)
            {
                case "success":
                    // Check if this is a handshake response
                    if (response.message.Contains("Handshake successful") && !isConnected)
                    {
                        isConnected = true;
                        onConnected?.Invoke();
                        LogMessage("Connected to haptics server");
                    }
                    else
                    {
                        LogMessage($"Server response: {response.message}", isVerboseLog: true);
                    }
                    break;
                    
                case "error":
                    LogError($"Server error: {response.message}");
                    break;
                    
                case "initiated":
                    LogMessage($"Server initiated: {response.message}");
                    break;
            }
        }
        catch (Exception e)
        {
            LogError($"Error processing server response: {e.Message}");
        }
    }

    /// <summary>
    /// Clean up resources.
    /// </summary>
    private void CleanUp()
    {
        // Stop receive thread
        isReceiving = false;
        
        if (receiveThread != null && receiveThread.IsAlive)
        {
            try
            {
                receiveThread.Abort();
            }
            catch (Exception)
            {
                // Ignore errors when aborting thread
            }
        }
        
        // Close UDP client
        if (udpClient != null)
        {
            try
            {
                udpClient.Close();
            }
            catch (Exception)
            {
                // Ignore errors when closing client
            }
            udpClient = null;
        }
        
        LogMessage("Resources cleaned up");
    }

    #endregion

    #region Utility Methods

    /// <summary>
    /// Send a command to the Python server.
    /// </summary>
    /// <param name="data">Dictionary containing command data</param>
    private void SendCommand(Dictionary<string, object> data)
{
    if (udpClient == null)
    {
        LogError("Cannot send command: UDP client is not initialized");
        return;
    }
    
    try
    {
        // Directly create JSON string using manual serialization - don't use JsonUtility
        string json = SerializeDictionary(data);
        
        // Log the actual JSON for debugging
        LogMessage($"Sending JSON: {json}", isVerboseLog: true);
        
        // Convert JSON to bytes
        byte[] bytes = Encoding.UTF8.GetBytes(json);
        
        // Send data to server
        udpClient.Send(bytes, bytes.Length, serverEndPoint);
        
        LogMessage($"Sent command: {data["command"]}", isVerboseLog: false);
    }
    catch (Exception e)
    {
        LogError($"Error sending command: {e.Message}");
    }
}

// Add this method for proper Dictionary serialization
private string SerializeDictionary(Dictionary<string, object> data)
{
    StringBuilder builder = new StringBuilder();
    builder.Append("{");
    
    bool first = true;
    foreach (var kvp in data)
    {
        if (!first)
            builder.Append(",");
            
        builder.Append("\"").Append(kvp.Key).Append("\":");
        
        // Handle different value types
        if (kvp.Value == null)
        {
            builder.Append("null");
        }
        else if (kvp.Value is string strValue)
        {
            builder.Append("\"").Append(strValue).Append("\"");
        }
        else if (kvp.Value is bool boolValue)
        {
            builder.Append(boolValue ? "true" : "false");
        }
        else if (kvp.Value is int || kvp.Value is float || kvp.Value is double)
        {
            builder.Append(kvp.Value.ToString());
        }
        else if (kvp.Value is Dictionary<string, string> dictValue)
        {
            builder.Append("{");
            bool innerFirst = true;
            foreach (var innerKvp in dictValue)
            {
                if (!innerFirst)
                    builder.Append(",");
                builder.Append("\"").Append(innerKvp.Key).Append("\":\"").Append(innerKvp.Value).Append("\"");
                innerFirst = false;
            }
            builder.Append("}");
        }
        else
        {
            // Default handling
            builder.Append("\"").Append(kvp.Value.ToString()).Append("\"");
        }
        
        first = false;
    }
    
    builder.Append("}");
    return builder.ToString();
}

    /// <summary>
    /// Log a message to the Unity console.
    /// </summary>
    /// <param name="message">Message to log</param>
    /// <param name="isVerboseLog">Whether this is a verbose log that should only be shown in debug mode</param>
    private void LogMessage(string message, bool isVerboseLog = false)
    {
        if (debugMode || !isVerboseLog)
        {
            Debug.Log($"[HapticsManager] {message}");
        }
    }

    /// <summary>
    /// Log an error to the Unity console.
    /// </summary>
    /// <param name="message">Error message to log</param>
    private void LogError(string message)
    {
        Debug.LogError($"[HapticsManager] {message}");
    }

    /// <summary>
    /// Log a haptic event to the Unity console.
    /// </summary>
    /// <param name="message">Event message to log</param>
    private void LogHapticEvent(string message)
    {
        if (logHapticEvents)
        {
            Debug.Log($"[Haptic Event] {message}");
        }
    }

    /// <summary>
    /// Manual parsing of JSON for older Unity versions without JsonUtility.
    /// </summary>
    /// <param name="jsonString">JSON string to parse</param>
    /// <returns>A ServerResponse object</returns>
    private ServerResponse ParseResponse(string jsonString)
    {
        ServerResponse response = new ServerResponse();
        
        try
        {
            // Simple string parsing for basic JSON
            if (jsonString.Contains("\"status\":\"success\""))
                response.status = "success";
            else if (jsonString.Contains("\"status\":\"error\""))
                response.status = "error";
            else if (jsonString.Contains("\"status\":\"initiated\""))
                response.status = "initiated";
            
            // Extract message
            int msgStart = jsonString.IndexOf("\"message\":\"") + 11;
            if (msgStart > 10)
            {
                int msgEnd = jsonString.IndexOf("\"", msgStart);
                if (msgEnd > msgStart)
                {
                    response.message = jsonString.Substring(msgStart, msgEnd - msgStart);
                }
            }
        }
        catch
        {
            // Default values in case of parsing failure
            response.status = "error";
            response.message = "Failed to parse server response";
        }
        
        return response;
    }

    #endregion

    #region Public Haptics API

    /// <summary>
    /// Activate a motor on the bHaptics gloves.
    /// </summary>
    /// <param name="glove">The glove to use ("left" or "right")</param>
    /// <param name="motorIndex">Index of the motor (0-5)</param>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    /// <param name="durationMs">Duration in milliseconds</param>
    public void ActivateGloveMotor(string glove = "left", int motorIndex = 0, int intensity = 100, int durationMs = 500)
    {
        if (!CheckConnection())
            return;
        
        Dictionary<string, object> data = new Dictionary<string, object>
        {
            { "command", "glove" },
            { "glove", glove },
            { "motor_index", motorIndex },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        SendCommand(data);
        LogHapticEvent($"Glove motor: {glove} #{motorIndex}, {intensity}%, {durationMs}ms");
        onHapticEffectPlayed?.Invoke();
    }

    /// <summary>
    /// Activate motors on the vest using the funnelling effect.
    /// </summary>
    /// <param name="panel">The panel to use ("front" or "back")</param>
    /// <param name="x">X coordinate (0.0-1.0, left to right)</param>
    /// <param name="y">Y coordinate (0.0-1.0, bottom to top)</param>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    /// <param name="durationMs">Duration in milliseconds</param>
    public void ActivateFunnellingEffect(string panel = "front", float x = 0.5f, float y = 0.5f, int intensity = 100, int durationMs = 500)
    {
        if (!CheckConnection())
            return;
        
        Dictionary<string, object> data = new Dictionary<string, object>
        {
            { "command", "funnel" },
            { "panel", panel },
            { "x", x },
            { "y", y },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        SendCommand(data);
        LogHapticEvent($"Funnel effect: {panel} ({x}, {y}), {intensity}%, {durationMs}ms");
        onHapticEffectPlayed?.Invoke();
    }

    /// <summary>
    /// Activate a specific motor on the vest using its index.
    /// </summary>
    /// <param name="panel">The panel to use ("front" or "back")</param>
    /// <param name="motorIndex">Index of the motor (0-19)</param>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    /// <param name="durationMs">Duration in milliseconds</param>
    public void ActivateDiscreteMotor(string panel = "front", int motorIndex = 0, int intensity = 100, int durationMs = 500)
    {
        if (!CheckConnection())
            return;
        
        Dictionary<string, object> data = new Dictionary<string, object>
        {
            { "command", "discrete" },
            { "panel", panel },
            { "motor_index", motorIndex },
            { "intensity", intensity },
            { "duration_ms", durationMs }
        };
        
        SendCommand(data);
        LogHapticEvent($"Discrete motor: {panel} #{motorIndex}, {intensity}%, {durationMs}ms");
        onHapticEffectPlayed?.Invoke();
    }

    /// <summary>
    /// Play a registered haptic pattern.
    /// </summary>
    /// <param name="keepAlive">Whether to keep the connection alive until the pattern completes</param>
    public void PlayHapticPattern(bool keepAlive = true)
    {
        if (!CheckConnection())
            return;
        
        Dictionary<string, object> data = new Dictionary<string, object>
        {
            { "command", "pattern" },
            { "keep_alive", keepAlive }
        };
        
        SendCommand(data);
        LogHapticEvent($"Playing haptic pattern (keep_alive={keepAlive})");
        onHapticEffectPlayed?.Invoke();
    }

    /// <summary>
    /// Check if the server is connected.
    /// </summary>
    /// <returns>True if connected, false otherwise</returns>
    public bool IsConnected()
    {
        return isConnected;
    }

    /// <summary>
    /// Check if the connection is established, show error if not.
    /// </summary>
    /// <returns>True if connected, false otherwise</returns>
    private bool CheckConnection()
    {
        if (!isConnected)
        {
            LogError("Cannot send command: Not connected to server");
            return false;
        }
        return true;
    }

    #endregion

    #region Example Haptic Patterns

    /// <summary>
    /// Play a heartbeat effect on the vest front.
    /// </summary>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    /// <param name="beats">Number of heartbeats to play</param>
    public void PlayHeartbeatEffect(int intensity = 100, int beats = 3)
    {
        StartCoroutine(HeartbeatSequence(intensity, beats));
    }

    /// <summary>
    /// Create a heartbeat sequence coroutine.
    /// </summary>
    private IEnumerator HeartbeatSequence(int intensity, int beats)
    {
        for (int i = 0; i < beats; i++)
        {
            // First beat (stronger)
            ActivateDiscreteMotor("front", 9, intensity, 200);
            
            yield return new WaitForSeconds(0.2f);
            
            // Second beat (weaker)
            ActivateDiscreteMotor("front", 9, intensity / 2, 150);
            
            // Wait before next heartbeat
            yield return new WaitForSeconds(0.8f);
        }
    }

    /// <summary>
    /// Create an impact effect at the specified location.
    /// </summary>
    /// <param name="panel">Panel to target ("front" or "back")</param>
    /// <param name="x">X coordinate (0.0-1.0)</param>
    /// <param name="y">Y coordinate (0.0-1.0)</param>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    public void PlayImpactEffect(string panel = "front", float x = 0.5f, float y = 0.5f, int intensity = 100)
    {
        StartCoroutine(ImpactSequence(panel, x, y, intensity));
    }

    /// <summary>
    /// Create an impact sequence coroutine.
    /// </summary>
    private IEnumerator ImpactSequence(string panel, float x, float y, int intensity)
    {
        // Initial strong impact
        ActivateFunnellingEffect(panel, x, y, intensity, 100);
        
        yield return new WaitForSeconds(0.1f);
        
        // Weaker follow-up
        ActivateFunnellingEffect(panel, x, y, intensity / 2, 150);
        
        yield return new WaitForSeconds(0.15f);
        
        // Final echo
        ActivateFunnellingEffect(panel, x, y, intensity / 4, 200);
    }

    /// <summary>
    /// Play a wave effect on the gloves.
    /// </summary>
    /// <param name="glove">Glove to target ("left", "right", or "both")</param>
    /// <param name="direction">Direction ("fingertip-to-palm" or "palm-to-fingertip")</param>
    /// <param name="intensity">Intensity of vibration (0-100)</param>
    public void PlayGloveWaveEffect(string glove = "both", string direction = "fingertip-to-palm", int intensity = 100)
    {
        StartCoroutine(GloveWaveSequence(glove, direction, intensity));
    }

    /// <summary>
    /// Create a glove wave sequence coroutine.
    /// </summary>
    private IEnumerator GloveWaveSequence(string glove, string direction, int intensity)
    {
        int[] motorSequence;
        
        // Determine sequence based on direction
        if (direction.ToLower() == "fingertip-to-palm")
        {
            motorSequence = new int[] { 1, 2, 3, 4, 5 };
        }
        else
        {
            motorSequence = new int[] { 5, 4, 3, 2, 1 };
        }
        
        // Determine which gloves to activate
        bool activateLeft = (glove.ToLower() == "left" || glove.ToLower() == "both");
        bool activateRight = (glove.ToLower() == "right" || glove.ToLower() == "both");
        
        // Play sequence
        foreach (int motorIndex in motorSequence)
        {
            if (activateLeft)
            {
                ActivateGloveMotor("left", motorIndex, intensity, 100);
            }
            
            if (activateRight)
            {
                ActivateGloveMotor("right", motorIndex, intensity, 100);
            }
            
            yield return new WaitForSeconds(0.1f);
        }
    }

    #endregion

    #region Helper Classes

    /// <summary>
    /// Class representing a response from the server.
    /// </summary>
    [System.Serializable]
    private class ServerResponse
    {
        public string status = "";
        public string message = "";
    }

    /// <summary>
    /// Wrapper class for serializing Dictionary to JSON.
    /// </summary>
    [System.Serializable]
    private class Wrapper
    {
        public string json;

        public Wrapper(Dictionary<string, object> data)
        {
            // Simple JSON serialization method for Dictionary
            System.Text.StringBuilder builder = new System.Text.StringBuilder();
            builder.Append("{");
            
            bool first = true;
            foreach (var kvp in data)
            {
                if (!first)
                    builder.Append(",");
                    
                // Key
                builder.Append("\"").Append(kvp.Key).Append("\":");
                
                // Value
                if (kvp.Value is string strValue)
                {
                    builder.Append("\"").Append(strValue).Append("\"");
                }
                else if (kvp.Value is bool boolValue)
                {
                    builder.Append(boolValue ? "true" : "false");
                }
                else if (kvp.Value is Dictionary<string, string> dictValue)
                {
                    builder.Append("{");
                    bool innerFirst = true;
                    foreach (var innerKvp in dictValue)
                    {
                        if (!innerFirst)
                            builder.Append(",");
                        builder.Append("\"").Append(innerKvp.Key).Append("\":\"").Append(innerKvp.Value).Append("\"");
                        innerFirst = false;
                    }
                    builder.Append("}");
                }
                else
                {
                    // Numbers, etc.
                    builder.Append(kvp.Value.ToString());
                }
                
                first = false;
            }
            
            builder.Append("}");
            json = builder.ToString();
        }
    }

    #endregion
}