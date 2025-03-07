using System.Collections;
using System.Collections.Generic;
using UnityEngine;
using Newtonsoft.Json.Linq;

/// <summary>
/// Helper class for creating custom haptic patterns for the bHaptics API.
/// Provides methods to create various common haptic effects.
/// </summary>
/// <remarks>
/// Author: Pi Ko (pi.ko@nyu.edu)
/// Date: March 7, 2025
/// </remarks>
public class HapticsPatternCreator : MonoBehaviour
{
    [Header("References")]
    [SerializeField] private UnifiedHapticsClient hapticsClient;
    
    [Header("Default Settings")]
    [SerializeField] private int defaultIntensity = 80;
    [SerializeField] private int defaultStepDuration = 100;
    
    /// <summary>
    /// Creates and plays a heartbeat pattern.
    /// Two strong pulses with a short delay between them.
    /// </summary>
    /// <param name="intensity">The maximum intensity (0-100).</param>
    /// <param name="repeats">Number of heartbeats.</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayHeartbeatPattern(int intensity = 0, int repeats = 3, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = defaultIntensity;
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        for (int i = 0; i < repeats; i++)
        {
            // First beat (stronger)
            pattern.Add(CreateCenterPulse(intensity));
            pattern.Add(CreateEmptyStep());
            
            // Second beat (slightly weaker)
            pattern.Add(CreateCenterPulse(intensity * 0.7f));
            
            // Pause before next heartbeat
            pattern.Add(CreateEmptyStep());
            pattern.Add(CreateEmptyStep());
        }
        
        // Play the pattern
        hapticsClient.PlayCustomPattern(pattern, defaultStepDuration, callback);
    }
    
    /// <summary>
    /// Creates and plays a circular pattern that rotates around the vest.
    /// </summary>
    /// <param name="clockwise">Whether to rotate clockwise or counterclockwise.</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="speed">Speed factor (higher = faster).</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayCircularPattern(bool clockwise = true, int intensity = 0, float speed = 1.0f, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = defaultIntensity;
        
        // Calculate step duration based on speed
        int stepDuration = Mathf.RoundToInt(defaultStepDuration / speed);
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // We'll create 8 steps for a full rotation
        int[][] motorSequence;
        
        if (clockwise)
        {
            motorSequence = new int[][] {
                new int[] { 0, 1 },       // Top right
                new int[] { 2, 3 },       // Top left
                new int[] { 4, 8 },       // Middle right
                new int[] { 5, 9 },       // Middle center-right
                new int[] { 6, 10 },      // Middle center-left
                new int[] { 7, 11 },      // Middle left
                new int[] { 12, 16 },     // Bottom right
                new int[] { 15, 19 }      // Bottom left
            };
        }
        else
        {
            motorSequence = new int[][] {
                new int[] { 2, 3 },       // Top left
                new int[] { 0, 1 },       // Top right
                new int[] { 7, 11 },      // Middle left
                new int[] { 6, 10 },      // Middle center-left
                new int[] { 5, 9 },       // Middle center-right
                new int[] { 4, 8 },       // Middle right
                new int[] { 15, 19 },     // Bottom left
                new int[] { 12, 16 }      // Bottom right
            };
        }
        
        // Generate the pattern steps
        foreach (int[] motors in motorSequence)
        {
            Dictionary<string, object> step = CreateEmptyStep();
            
            // Activate the specific motors for this step
            foreach (int motor in motors)
            {
                // Activate on both front and back
                ((int[][])step["front"])[motor / 4][motor % 4] = intensity;
                ((int[][])step["back"])[motor / 4][motor % 4] = intensity;
            }
            
            pattern.Add(step);
        }
        
        // Play the pattern
        hapticsClient.PlayCustomPattern(pattern, stepDuration, callback);
    }
    
    /// <summary>
    /// Creates and plays an impact pattern that radiates from the point of impact.
    /// </summary>
    /// <param name="panel">The panel ('front' or 'back').</param>
    /// <param name="x">X coordinate of impact (0-1).</param>
    /// <param name="y">Y coordinate of impact (0-1).</param>
    /// <param name="intensity">The maximum intensity (0-100).</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayImpactPattern(string panel, float x, float y, int intensity = 0, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = defaultIntensity;
        
        // Convert coordinates to motor indices
        int col = Mathf.Clamp(Mathf.FloorToInt(x * 4), 0, 3);
        int row = Mathf.Clamp(Mathf.FloorToInt(y * 5), 0, 4);
        int centerMotor = row * 4 + col;
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Step 1: Strong pulse at center
        Dictionary<string, object> step1 = CreateEmptyStep();
        ((int[][])step1[panel])[row][col] = intensity;
        pattern.Add(step1);
        
        // Step 2: Medium pulse at adjacent motors
        Dictionary<string, object> step2 = CreateEmptyStep();
        int mediumIntensity = Mathf.RoundToInt(intensity * 0.7f);
        
        // Activate adjacent motors
        for (int r = row - 1; r <= row + 1; r++)
        {
            for (int c = col - 1; c <= col + 1; c++)
            {
                if (r >= 0 && r < 5 && c >= 0 && c < 4)
                {
                    // Don't include the center motor
                    if (r != row || c != col)
                    {
                        ((int[][])step2[panel])[r][c] = mediumIntensity;
                    }
                }
            }
        }
        pattern.Add(step2);
        
        // Step 3: Weak pulse at outer ring
        Dictionary<string, object> step3 = CreateEmptyStep();
        int weakIntensity = Mathf.RoundToInt(intensity * 0.4f);
        
        // Activate outer ring motors
        for (int r = row - 2; r <= row + 2; r++)
        {
            for (int c = col - 2; c <= col + 2; c++)
            {
                if (r >= 0 && r < 5 && c >= 0 && c < 4)
                {
                    // Only include motors that are 2 steps away from center
                    int distance = Mathf.Abs(r - row) + Mathf.Abs(c - col);
                    if (distance == 2)
                    {
                        ((int[][])step3[panel])[r][c] = weakIntensity;
                    }
                }
            }
        }
        pattern.Add(step3);
        
        // Play the pattern
        hapticsClient.PlayCustomPattern(pattern, defaultStepDuration, callback);
    }
    
    /// <summary>
    /// Creates and plays a rain pattern with random droplets.
    /// </summary>
    /// <param name="duration">Duration in seconds.</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="density">How many droplets per second (1-10).</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayRainPattern(float duration = 3.0f, int intensity = 0, int density = 5, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = Mathf.RoundToInt(defaultIntensity * 0.6f);
        density = Mathf.Clamp(density, 1, 10);
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Calculate number of steps based on duration and density
        int steps = Mathf.RoundToInt(duration * density);
        
        for (int i = 0; i < steps; i++)
        {
            Dictionary<string, object> step = CreateEmptyStep();
            
            // Add 1-3 random raindrops to the back panel primarily
            int drops = Random.Range(1, 4);
            for (int d = 0; d < drops; d++)
            {
                int row = Random.Range(0, 5);
                int col = Random.Range(0, 4);
                
                // Randomize intensity slightly
                int dropIntensity = Mathf.RoundToInt(intensity * Random.Range(0.8f, 1.2f));
                dropIntensity = Mathf.Clamp(dropIntensity, 0, 100);
                
                // Usually on back, occasionally on front
                string panel = Random.value < 0.9f ? "back" : "front";
                ((int[][])step[panel])[row][col] = dropIntensity;
            }
            
            pattern.Add(step);
        }
        
        // Play the pattern with faster step duration for rain
        int rainStepDuration = Mathf.RoundToInt(defaultStepDuration * 0.7f);
        hapticsClient.PlayCustomPattern(pattern, rainStepDuration, callback);
    }
    
    /// <summary>
    /// Creates and plays a wave pattern that moves from top to bottom.
    /// </summary>
    /// <param name="panel">The panel ('front', 'back', or 'both').</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayWavePattern(string panel = "both", int intensity = 0, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = defaultIntensity;
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Create 5 steps (one for each row)
        for (int row = 0; row < 5; row++)
        {
            Dictionary<string, object> step = CreateEmptyStep();
            
            // Activate all motors in this row
            for (int col = 0; col < 4; col++)
            {
                if (panel == "front" || panel == "both")
                {
                    ((int[][])step["front"])[row][col] = intensity;
                }
                
                if (panel == "back" || panel == "both")
                {
                    ((int[][])step["back"])[row][col] = intensity;
                }
            }
            
            pattern.Add(step);
        }
        
        // Play the pattern
        hapticsClient.PlayCustomPattern(pattern, defaultStepDuration, callback);
    }
    
    /// <summary>
    /// Creates and plays a pulse pattern that alternates between front and back.
    /// </summary>
    /// <param name="pulses">Number of pulses.</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayPulsePattern(int pulses = 5, int intensity = 0, System.Action<JObject> callback = null)
    {
        if (intensity <= 0) intensity = defaultIntensity;
        
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        for (int i = 0; i < pulses; i++)
        {
            // Add front pulse
            Dictionary<string, object> frontStep = CreateEmptyStep();
            for (int row = 0; row < 5; row++)
            {
                for (int col = 0; col < 4; col++)
                {
                    ((int[][])frontStep["front"])[row][col] = intensity;
                }
            }
            pattern.Add(frontStep);
            
            // Add empty step (pause)
            pattern.Add(CreateEmptyStep());
            
            // Add back pulse
            Dictionary<string, object> backStep = CreateEmptyStep();
            for (int row = 0; row < 5; row++)
            {
                for (int col = 0; col < 4; col++)
                {
                    ((int[][])backStep["back"])[row][col] = intensity;
                }
            }
            pattern.Add(backStep);
            
            // Add empty step (pause)
            pattern.Add(CreateEmptyStep());
        }
        
        // Play the pattern
        hapticsClient.PlayCustomPattern(pattern, defaultStepDuration, callback);
    }
    
    #region Helper Methods
    
    /// <summary>
    /// Creates an empty step with all motors set to 0.
    /// </summary>
    /// <returns>A step dictionary with front and back arrays.</returns>
    private Dictionary<string, object> CreateEmptyStep()
    {
        Dictionary<string, object> step = new Dictionary<string, object>();
        
        // Create front panel array
        int[][] frontPanel = new int[5][];
        for (int row = 0; row < 5; row++)
        {
            frontPanel[row] = new int[4] { 0, 0, 0, 0 };
        }
        
        // Create back panel array
        int[][] backPanel = new int[5][];
        for (int row = 0; row < 5; row++)
        {
            backPanel[row] = new int[4] { 0, 0, 0, 0 };
        }
        
        step["front"] = frontPanel;
        step["back"] = backPanel;
        
        return step;
    }
    
    /// <summary>
    /// Creates a step with a pulse in the center of both panels.
    /// </summary>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <returns>A step dictionary with a pulse in the center.</returns>
    private Dictionary<string, object> CreateCenterPulse(float intensity)
    {
        Dictionary<string, object> step = CreateEmptyStep();
        
        // Center motors (middle of the vest)
        int[] centerRows = { 1, 2, 3 };
        int[] centerCols = { 1, 2 };
        
        // Activate center motors
        foreach (int row in centerRows)
        {
            foreach (int col in centerCols)
            {
                ((int[][])step["front"])[row][col] = Mathf.RoundToInt(intensity);
                ((int[][])step["back"])[row][col] = Mathf.RoundToInt(intensity);
            }
        }
        
        return step;
    }
    
    /// <summary>
    /// Creates a step with motors activated in a horizontal line.
    /// </summary>
    /// <param name="row">The row to activate (0-4).</param>
    /// <param name="panel">The panel ('front', 'back', or 'both').</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <returns>A step dictionary with the specified row activated.</returns>
    private Dictionary<string, object> CreateHorizontalLine(int row, string panel, float intensity)
    {
        Dictionary<string, object> step = CreateEmptyStep();
        
        // Clamp row
        row = Mathf.Clamp(row, 0, 4);
        
        // Activate all motors in this row
        for (int col = 0; col < 4; col++)
        {
            if (panel == "front" || panel == "both")
            {
                ((int[][])step["front"])[row][col] = Mathf.RoundToInt(intensity);
            }
            
            if (panel == "back" || panel == "both")
            {
                ((int[][])step["back"])[row][col] = Mathf.RoundToInt(intensity);
            }
        }
        
        return step;
    }
    
    /// <summary>
    /// Creates a step with motors activated in a vertical line.
    /// </summary>
    /// <param name="col">The column to activate (0-3).</param>
    /// <param name="panel">The panel ('front', 'back', or 'both').</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <returns>A step dictionary with the specified column activated.</returns>
    private Dictionary<string, object> CreateVerticalLine(int col, string panel, float intensity)
    {
        Dictionary<string, object> step = CreateEmptyStep();
        
        // Clamp column
        col = Mathf.Clamp(col, 0, 3);
        
        // Activate all motors in this column
        for (int row = 0; row < 5; row++)
        {
            if (panel == "front" || panel == "both")
            {
                ((int[][])step["front"])[row][col] = Mathf.RoundToInt(intensity);
            }
            
            if (panel == "back" || panel == "both")
            {
                ((int[][])step["back"])[row][col] = Mathf.RoundToInt(intensity);
            }
        }
        
        return step;
    }
    
    #endregion
    
    #region Public Utility Methods
    
    /// <summary>
    /// Creates a custom pattern that can be saved and reused.
    /// </summary>
    /// <param name="steps">The number of steps in the pattern.</param>
    /// <returns>A list of empty pattern steps.</returns>
    public List<Dictionary<string, object>> CreateEmptyPattern(int steps)
    {
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        for (int i = 0; i < steps; i++)
        {
            pattern.Add(CreateEmptyStep());
        }
        
        return pattern;
    }
    
    /// <summary>
    /// Sets a specific motor in a pattern step.
    /// </summary>
    /// <param name="pattern">The pattern to modify.</param>
    /// <param name="stepIndex">The step index to modify.</param>
    /// <param name="panel">The panel ('front' or 'back').</param>
    /// <param name="motorIndex">The motor index (0-19).</param>
    /// <param name="intensity">The intensity (0-100).</param>
    public void SetMotor(List<Dictionary<string, object>> pattern, int stepIndex, string panel, int motorIndex, int intensity)
    {
        if (stepIndex < 0 || stepIndex >= pattern.Count)
            return;
            
        if (motorIndex < 0 || motorIndex >= 20)
            return;
            
        if (panel != "front" && panel != "back")
            return;
            
        // Calculate row and column
        int row = motorIndex / 4;
        int col = motorIndex % 4;
        
        // Set the intensity
        ((int[][])pattern[stepIndex][panel])[row][col] = intensity;
    }
    
    /// <summary>
    /// Sets a motor using row and column coordinates.
    /// </summary>
    /// <param name="pattern">The pattern to modify.</param>
    /// <param name="stepIndex">The step index to modify.</param>
    /// <param name="panel">The panel ('front' or 'back').</param>
    /// <param name="row">The row (0-4).</param>
    /// <param name="col">The column (0-3).</param>
    /// <param name="intensity">The intensity (0-100).</param>
    public void SetMotorRC(List<Dictionary<string, object>> pattern, int stepIndex, string panel, int row, int col, int intensity)
    {
        if (stepIndex < 0 || stepIndex >= pattern.Count)
            return;
            
        if (row < 0 || row >= 5 || col < 0 || col >= 4)
            return;
            
        if (panel != "front" && panel != "back")
            return;
            
        // Set the intensity
        ((int[][])pattern[stepIndex][panel])[row][col] = intensity;
    }
    
    /// <summary>
    /// Plays a custom pattern.
    /// </summary>
    /// <param name="pattern">The pattern to play.</param>
    /// <param name="stepDuration">The duration of each step in milliseconds.</param>
    /// <param name="callback">Optional callback for completion.</param>
    public void PlayCustomPattern(List<Dictionary<string, object>> pattern, int stepDuration = 0, System.Action<JObject> callback = null)
    {
        if (stepDuration <= 0) stepDuration = defaultStepDuration;
        
        hapticsClient.PlayCustomPattern(pattern, stepDuration, callback);
    }
    
    #endregion
    
    #region Game-Specific Haptic Effects
    
    /// <summary>
    /// Creates a haptic effect for player damage.
    /// </summary>
    /// <param name="damageDirection">Direction of the damage (0-360 degrees, 0 = front).</param>
    /// <param name="intensity">The intensity based on damage amount (0-100).</param>
    public void PlayDamageEffect(float damageDirection, int intensity = 80)
    {
        // Determine which panel to use based on direction
        string panel;
        if (damageDirection >= 315 || damageDirection < 45 || (damageDirection >= 135 && damageDirection < 225))
        {
            // Front or back
            panel = (damageDirection >= 135 && damageDirection < 225) ? "back" : "front";
        }
        else
        {
            // Side shots alternate between front and back to create a side effect
            panel = "both";
            intensity = Mathf.RoundToInt(intensity * 0.7f); // Reduce intensity for both panels
        }
        
        // Convert direction to impact coordinates
        float x, y;
        
        if (damageDirection >= 315 || damageDirection < 45)
        {
            // Front center
            x = 0.5f;
            y = 0.5f;
        }
        else if (damageDirection >= 45 && damageDirection < 135)
        {
            // Right side
            x = 0.9f;
            y = 0.5f;
        }
        else if (damageDirection >= 135 && damageDirection < 225)
        {
            // Back center
            x = 0.5f;
            y = 0.5f;
        }
        else
        {
            // Left side
            x = 0.1f;
            y = 0.5f;
        }
        
        // Play an impact pattern at this location
        PlayImpactPattern(panel, x, y, intensity);
    }
    
    /// <summary>
    /// Creates a haptic effect for player healing.
    /// </summary>
    /// <param name="intensity">The intensity based on healing amount (0-100).</param>
    public void PlayHealingEffect(int intensity = 60)
    {
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Gentle waves moving up from bottom
        for (int row = 4; row >= 0; row--)
        {
            Dictionary<string, object> step = CreateEmptyStep();
            
            // Create a horizontal line that gets stronger as it moves upward
            float rowIntensity = Mathf.Lerp(intensity * 0.5f, intensity, 1f - (row / 4f));
            
            // Activate all motors in this row
            for (int col = 0; col < 4; col++)
            {
                ((int[][])step["front"])[row][col] = Mathf.RoundToInt(rowIntensity);
                ((int[][])step["back"])[row][col] = Mathf.RoundToInt(rowIntensity * 0.7f);
            }
            
            pattern.Add(step);
        }
        
        // Add a gentle full-body pulse at the end
        Dictionary<string, object> finalStep = CreateEmptyStep();
        for (int row = 0; row < 5; row++)
        {
            for (int col = 0; col < 4; col++)
            {
                ((int[][])finalStep["front"])[row][col] = Mathf.RoundToInt(intensity * 0.7f);
                ((int[][])finalStep["back"])[row][col] = Mathf.RoundToInt(intensity * 0.5f);
            }
        }
        pattern.Add(finalStep);
        
        // Play the pattern with slightly longer duration for a soothing effect
        int healStepDuration = Mathf.RoundToInt(defaultStepDuration * 1.5f);
        hapticsClient.PlayCustomPattern(pattern, healStepDuration);
    }
    
    /// <summary>
    /// Creates a haptic effect for environmental hazards like fire.
    /// </summary>
    /// <param name="duration">Duration in seconds.</param>
    /// <param name="intensity">The intensity (0-100).</param>
    public void PlayFireEffect(float duration = 3.0f, int intensity = 70)
    {
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Calculate number of steps based on duration
        int steps = Mathf.RoundToInt(duration * 5);  // 5 steps per second
        
        for (int i = 0; i < steps; i++)
        {
            Dictionary<string, object> step = CreateEmptyStep();
            
            // Chaotic fire patterns with more intensity at the bottom
            for (int row = 0; row < 5; row++)
            {
                // More intensity at the bottom rows to simulate rising flames
                float rowFactor = 1.0f - ((float)row / 5f) * 0.7f;
                
                for (int col = 0; col < 4; col++)
                {
                    // Random intensity variations
                    if (Random.value < 0.4f * rowFactor)
                    {
                        int fireIntensity = Mathf.RoundToInt(intensity * Random.Range(0.6f, 1.0f) * rowFactor);
                        ((int[][])step["front"])[row][col] = fireIntensity;
                    }
                    
                    // Less intensity on the back
                    if (Random.value < 0.3f * rowFactor)
                    {
                        int fireIntensity = Mathf.RoundToInt(intensity * Random.Range(0.4f, 0.8f) * rowFactor);
                        ((int[][])step["back"])[row][col] = fireIntensity;
                    }
                }
            }
            
            pattern.Add(step);
        }
        
        // Fire should have shorter, more erratic pulses
        int fireStepDuration = Mathf.RoundToInt(defaultStepDuration * 0.6f);
        hapticsClient.PlayCustomPattern(pattern, fireStepDuration);
    }
    
    /// <summary>
    /// Creates a haptic effect for water/swimming.
    /// </summary>
    /// <param name="duration">Duration in seconds.</param>
    /// <param name="intensity">The intensity (0-100).</param>
    /// <param name="swimSpeed">Swimming speed factor (0-2).</param>
    public void PlaySwimmingEffect(float duration = 5.0f, int intensity = 40, float swimSpeed = 1.0f)
    {
        // Create the pattern steps
        List<Dictionary<string, object>> pattern = new List<Dictionary<string, object>>();
        
        // Calculate number of cycles based on duration and swim speed
        float cycleTime = 2.0f / swimSpeed;
        int cycles = Mathf.CeilToInt(duration / cycleTime);
        
        for (int cycle = 0; cycle < cycles; cycle++)
        {
            // Left arm stroke
            pattern.Add(CreateVerticalLine(0, "both", intensity * 0.8f));
            pattern.Add(CreateEmptyStep());
            
            // Right arm stroke
            pattern.Add(CreateVerticalLine(3, "both", intensity * 0.8f));
            pattern.Add(CreateEmptyStep());
            
            // Gentle body movement
            Dictionary<string, object> bodyStep = CreateEmptyStep();
            for (int row = 1; row < 4; row++)
            {
                for (int col = 1; col < 3; col++)
                {
                    ((int[][])bodyStep["front"])[row][col] = Mathf.RoundToInt(intensity * 0.5f);
                    ((int[][])bodyStep["back"])[row][col] = Mathf.RoundToInt(intensity * 0.5f);
                }
            }
            pattern.Add(bodyStep);
            
            // Pause before next cycle
            pattern.Add(CreateEmptyStep());
        }
        
        // Swimming should have smooth transitions
        int swimStepDuration = Mathf.RoundToInt(defaultStepDuration * (1.5f / swimSpeed));
        hapticsClient.PlayCustomPattern(pattern, swimStepDuration);
    }
    
    #endregion
}

