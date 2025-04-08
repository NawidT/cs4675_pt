// Interface for LLM responses
export interface LLMResponse {
  text: string;
  timestamp: Date;
}

// Interface for LLM service
export interface LLMService {
  sendMessage(message: string): Promise<LLMResponse>;
  clearHistory(): void;
}

// Gemini implementation
export class GeminiService implements LLMService {
  private apiKey: string;
  private model: string;
  private history: Array<{ role: 'user' | 'model'; parts: { text: string }[] }>;

  constructor(apiKey: string, model: string = 'gemini-2.0-flash') {
    this.apiKey = apiKey;
    this.model = model;
    this.history = [];

    // Initialize with system prompt
    this.history.push({
      role: 'user',
      parts: [{
        text: `You are PT (Personal Transformer), an AI-powered nutrition and fitness assistant. Your role is to:
1. Provide personalized meal plans and nutritional advice
2. Consider user's dietary restrictions, health conditions, and preferences
3. Adapt recommendations based on user feedback
4. Offer continuous guidance and support
5. Focus on evidence-based nutritional information

When interacting with users:
- Ask about their health goals, dietary restrictions, and preferences
- Provide specific, actionable advice
- Explain the reasoning behind your recommendations
- Be supportive and encouraging
- Maintain a professional yet friendly tone

Remember to:
- Never provide medical advice
- Always recommend consulting healthcare professionals for medical concerns
- Focus on general wellness and nutrition guidance
- Be clear about the limitations of AI-generated advice`
      }]
    });
  }

  clearHistory(): void {
    this.history = [];
    // Re-initialize with system prompt after clearing
    this.history.push({
      role: 'user',
      parts: [{
        text: `You are PT (Personal Transformer), an AI-powered nutrition and fitness assistant. Your role is to:
1. Provide personalized meal plans and nutritional advice
2. Consider user's dietary restrictions, health conditions, and preferences
3. Adapt recommendations based on user feedback
4. Offer continuous guidance and support
5. Focus on evidence-based nutritional information

When interacting with users:
- Ask about their health goals, dietary restrictions, and preferences
- Provide specific, actionable advice
- Explain the reasoning behind your recommendations
- Be supportive and encouraging
- Maintain a professional yet friendly tone

Remember to:
- Never provide medical advice
- Always recommend consulting healthcare professionals for medical concerns
- Focus on general wellness and nutrition guidance
- Be clear about the limitations of AI-generated advice`
      }]
    });
  }

  async sendMessage(message: string): Promise<LLMResponse> {
    try {
      // Add user message to history
      this.history.push({
        role: 'user',
        parts: [{ text: message }]
      });

      const response = await fetch(`https://generativelanguage.googleapis.com/v1beta/models/${this.model}:generateContent?key=${this.apiKey}`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          contents: this.history,
          generationConfig: {
            temperature: 0.7,
            topK: 40,
            topP: 0.95,
            maxOutputTokens: 1024,
          }
        }),
      });

      if (!response.ok) {
        const errorData = await response.json();
        console.error('Gemini API Error:', errorData);
        throw new Error(`Failed to get response from Gemini: ${errorData.error?.message || response.statusText}`);
      }

      const data = await response.json();
      
      if (!data.candidates?.[0]?.content?.parts?.[0]?.text) {
        console.error('Unexpected Gemini response format:', data);
        throw new Error('Invalid response format from Gemini');
      }

      const aiResponse = data.candidates[0].content.parts[0].text;

      // Add AI response to history
      this.history.push({
        role: 'model',
        parts: [{ text: aiResponse }]
      });

      return {
        text: aiResponse,
        timestamp: new Date()
      };
    } catch (error) {
      console.error('Error calling Gemini:', error);
      throw error;
    }
  }
}

// Example of how to implement another LLM service
/*
export class OpenAIService implements LLMService {
  async sendMessage(message: string): Promise<LLMResponse> {
    // OpenAI implementation
  }
}
*/ 