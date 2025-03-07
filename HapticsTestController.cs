using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using UnityEngine.UI;
using Newtonsoft.Json.Linq;
using TMPro;

/// <summary>
/// Test controller for the bHaptics API.
/// Demonstrates how to use the UnifiedHapticsClient to control haptic feedback in a Unity application.
/// </summary>
/// <remarks>
/// Author: Pi Ko (pi.ko@nyu.edu)
/// Date: March 7, 2025
/// </remarks>
public class HapticsTestController : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private UnifiedHapticsClient hapticsClient;
    [SerializeField] private TextMeshProUGUI statusText;
    [SerializeField] private TextMeshProUGUI feedbackText;
    [SerializeField] private TextMeshProUGUI commandResponseText;
    
    [Header("Test Settings")]
    [SerializeField] private int defaultIntensity = 50;
    [SerializeField] private int defaultDuration = 300;
    
    [Header("Vest Controls")]
    [SerializeField] private Button[] frontMotorButtons = new Button[20];
    [SerializeField] private Button[] backMotorButtons = new Button[20];
    [SerializeField] private Slider intensitySlider;
    [SerializeField] private Slider durationSlider;
    [SerializeField] private Toggle funnellingToggle;
    
    [Header("Glove Controls")]
    [SerializeField] private Button[] leftGloveButtons = new Button[6]; 
    [SerializeField] private Button[] rightGloveButtons = new Button[6];
    
    [Header("Pattern Controls")]
    [SerializeField] private Button wavePatternButton;
    [SerializeField] private Button alternatingPatternButton;
    [SerializeField] private Button stopPatternsButton;
    
    private bool usingFunnelling = false;
    private Vector3 frontPanelPosition;
    private Vector3 backPanelPosition;
    
    private void Start()
    {
        // Initialize UI
        SetupUI();
        
        // Register event handlers
        RegisterEventHandlers();
        
        // Update status text
        UpdateStatus("Initializing...");
    }
    
    private void SetupUI()
    {
        // Set initial values
        if (intensitySlider != null)
        {
            intensitySlider.value = defaultIntensity;
        }
        
        if (durationSlider != null)
        {
            durationSlider.value = defaultDuration;
        }
        
        if (funnellingToggle != null)
        {
            funnellingToggle.isOn = usingFunnelling;
            funnellingToggle.onValueChanged.AddListener(OnFunnellingToggleChanged);
        }
        
        // Setup vest motor buttons
        SetupMotorButtons(frontMotorButtons, "front", frontPanelPosition);
        SetupMotorButtons(backMotorButtons, "back", backPanelPosition);
        
        // Setup glove buttons
        SetupGloveButtons(leftGloveButtons, "left");
        SetupGloveButtons(rightGloveButtons, "right");
        
        // Setup pattern buttons
        if (wavePatternButton != null)
        {
            wavePatternButton.onClick.AddListener(OnWavePatternButtonClicked);
        }
        
        if (alternatingPatternButton != null)
        {
            alternatingPatternButton.onClick.AddListener(OnAlternatingPatternButtonClicked);
        }
        
        if (stopPatternsButton != null)
        {
            stopPatternsButton.onClick.AddListener(OnStopPatternsButtonClicked);
        }
    }
    
    private void SetupMotorButtons(Button[] buttons, string panel, Vector3 panelPosition)
    {
        for (int i = 0; i < buttons.Length; i++)
        {
            if (buttons[i] != null)
            {
                int motorIndex = i; // Capture the index for the lambda
                
                // Add onClick listener
                buttons[i].onClick.AddListener(() =>
                {
                    ActivateMotor(panel, motorIndex);
                });
                
                // Also add hover listener (using EventTrigger)
                var trigger = buttons[i].gameObject.AddComponent<EventTrigger>();
                var pointerEnter = new EventTrigger.Entry { eventID = EventTriggerType.PointerEnter };
                pointerEnter.callback.AddListener((data) =>
                {
                    if (usingFunnelling)
                    {
                        // Calculate normalized coordinates
                        RectTransform buttonRect = buttons[motorIndex].GetComponent<RectTransform>();
                        if (buttonRect != null)
                        {
                            // Map the motor's position to normalized 0-1 coordinates
                            // This assumes your UI layout matches the vest's motor layout
                            int row = motorIndex / 4;
                            int col = motorIndex % 4;
                            
                            float x = (float)col / 3.0f;  // 4 columns, normalized to 0-1
                            float y = (float)row / 4.0f;  // 5 rows, normalized to 0-1
                            
                            ActivateFunnelling(panel, x, y);
                        }
                    }
                });
                trigger.triggers.Add(pointerEnter);
            }
        }
    }
    
    private void SetupGloveButtons(Button[] buttons, string glove)
    {
        for (int i = 0; i < buttons.Length; i++)
        {
            if (buttons[i] != null)
            {
                int motorIndex = i; // Capture the index for the lambda
                
                // Add onClick listener
                buttons[i].onClick.AddListener(() =>
                {
                    ActivateGloveMotor(glove, motorIndex);
                });
            }
        }
    }
    
    private void RegisterEventHandlers()
    {
        // Register for pattern completion events
        hapticsClient.RegisterEventHandler("pattern_complete", OnPatternComplete);
        hapticsClient.RegisterEventHandler("pattern_error", OnPatternError);
    }
    
    private void OnPatternComplete(JObject data)
    {
        string patternType = data["pattern_type"]?.ToString() ?? "unknown";
        ShowFeedback($"Pattern complete: {patternType}");
    }
    
    private void OnPatternError(JObject data)
    {
        string patternType = data["pattern_type"]?.ToString() ?? "unknown";
        string error = data["error"]?.ToString() ?? "unknown error";
        ShowFeedback($"Pattern error ({patternType}): {error}");
    }
    
    private void OnFunnellingToggleChanged(bool isOn)
    {
        usingFunnelling = isOn;
        ShowFeedback($"Switched to {(usingFunnelling ? "funnelling" : "discrete")} mode");
    }
    
    // Event Handlers for UI
    
    public void OnConnectButtonClicked()
    {
        hapticsClient.ConnectToServer();
        UpdateStatus("Connecting...");
    }
    
    public void OnDisconnectButtonClicked()
    {
        hapticsClient.Disconnect();
        UpdateStatus("Disconnected");
    }
    
    public void OnCheckStatusButtonClicked()
    {
        hapticsClient.GetDeviceStatus(null, OnStatusResponse);
    }
    
    public void OnWavePatternButtonClicked()
    {
        hapticsClient.PlayWavePattern(OnPatternStartResponse);
    }
    
    public void OnAlternatingPatternButtonClicked()
    {
        hapticsClient.PlayAlternatingPattern(OnPatternStartResponse);
    }
    
    public void OnStopPatternsButtonClicked()
    {
        hapticsClient.StopPattern(null, (response) =>
        {
            bool success = response["success"]?.ToObject<bool>() ?? false;
            ShowFeedback(success ? "All patterns stopped" : "Failed to stop patterns");
        });
    }
    
    // Haptic Feedback Methods
    
    private void ActivateMotor(string panel, int motorIndex)
    {
        int intensity = (int)intensitySlider.value;
        int duration = (int)durationSlider.value;
        
        if (usingFunnelling)
        {
            // Convert motor index to x,y coordinates
            int row = motorIndex / 4;
            int col = motorIndex % 4;
            
            float x = (float)col / 3.0f;  // 4 columns, normalized to 0-1
            float y = (float)row / 4.0f;  // 5 rows, normalized to 0-1
            
            hapticsClient.ActivateFunnelling(panel, x, y, intensity, duration, OnMotorActivationResponse);
        }
        else
        {
            hapticsClient.ActivateDiscreteMotor(panel, motorIndex, intensity, duration, OnMotorActivationResponse);
        }
        
        ShowFeedback($"Activated {panel} motor {motorIndex} at {intensity}% for {duration}ms");
    }
    
    private void ActivateFunnelling(string panel, float x, float y)
    {
        int intensity = (int)intensitySlider.value;
        int duration = (int)durationSlider.value;
        
        hapticsClient.ActivateFunnelling(panel, x, y, intensity, duration, OnMotorActivationResponse);
        
        ShowFeedback($"Activated {panel} funnelling at ({x:F2}, {y:F2}) at {intensity}% for {duration}ms");
    }
    
    private void ActivateGloveMotor(string glove, int motorIndex)
    {
        int intensity = (int)intensitySlider.value;
        int duration = (int)durationSlider.value;
        
        hapticsClient.ActivateGloveMotor(glove, motorIndex, intensity, duration, OnMotorActivationResponse);
        
        ShowFeedback($"Activated {glove} glove motor {motorIndex} at {intensity}% for {duration}ms");
    }
    
    // Response Callbacks
    
    private void OnMotorActivationResponse(JObject response)
    {
        bool success = response["success"]?.ToObject<bool>() ?? false;
        
        if (!success)
        {
            string error = response["error"]?.ToString() ?? "Unknown error";
            ShowFeedback($"Motor activation failed: {error}");
        }
        
        // Show the raw response
        ShowCommandResponse(response.ToString());
    }
    
    private void OnPatternStartResponse(JObject response)
    {
        bool success = response["success"]?.ToObject<bool>() ?? false;
        string message = response["message"]?.ToString() ?? "Unknown response";
        
        ShowFeedback(success ? message : $"Pattern start failed: {response["error"]}");
        ShowCommandResponse(response.ToString());
    }
    
    private void OnStatusResponse(JObject response)
    {
        ShowCommandResponse(response.ToString());
        
        // Update connection status based on device connections
        if (response["devices"] is JObject devices)
        {
            bool vestConnected = devices["vest"]?.ToObject<bool>() ?? false;
            bool gloveLeftConnected = devices["glove_left"]?.ToObject<bool>() ?? false;
            bool gloveRightConnected = devices["glove_right"]?.ToObject<bool>() ?? false;
            
            string statusMsg = $"Vest: {(vestConnected ? "✓" : "✗")} | " +
                               $"Left Glove: {(gloveLeftConnected ? "✓" : "✗")} | " +
                               $"Right Glove: {(gloveRightConnected ? "✓" : "✗")}";
            
            UpdateStatus(statusMsg);
        }
    }
    
    // UI Update Methods
    
    private void UpdateStatus(string status)
    {
        if (statusText != null)
        {
            statusText.text = status;
        }
    }
    
    private void ShowFeedback(string feedback)
    {
        if (feedbackText != null)
        {
            feedbackText.text = feedback;
            
            // Auto-clear after 3 seconds
            StartCoroutine(ClearTextAfterDelay(feedbackText, 3f));
        }
    }
    
    private void ShowCommandResponse(string response)
    {
        if (commandResponseText != null)
        {
            commandResponseText.text = response;
        }
    }
    
    private IEnumerator ClearTextAfterDelay(TextMeshProUGUI textComponent, float delay)
    {
        yield return new WaitForSeconds(delay);
        textComponent.text = "";
    }
    
    // Unity Lifecycle
    
    private void OnDestroy()
    {
        // Unregister event handlers to prevent memory leaks
        if (hapticsClient != null)
        {
            hapticsClient.UnregisterEventHandler("pattern_complete");
            hapticsClient.UnregisterEventHandler("pattern_error");
        }
    }
}