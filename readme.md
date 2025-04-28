# Personal Transformer (PT) 🏋️‍♂️

Personal Transformer (PT) is an intelligent fitness companion that leverages RAG (Retrieval-Augmented Generation) technology to provide personalized fitness guidance and maintain ongoing conversations about your health journey.

## Features

- **Personalized Fitness Chat**: Engage in natural conversations about your fitness goals, routines, and progress
- **Long-term Memory**: Maintains context of your previous conversations and fitness journey
- **Firebase Integration**: Secure storage of user data and chat history
- **RAG Technology**: Combines knowledge retrieval with conversational AI for accurate, contextual responses
- **Progress Tracking**: Keep track of your fitness milestones and achievements

## Technical Stack

- Langchain for Ease of AI interactions
- Firebase Realtime Database for RAG (Retrieval-Augmented Generation)
- Flask to run our Python API
- React.js as our frontend framework
- Vercel to host our frontend on https://cs4675pt.vercel.app/
- Railway to host our backend and handle CI/CD automatically

## System Design Overview
![Draw.io for the System Design](https://github.com/NawidT/cs4675_pt/blob/main/assets/system_design.png)

## Getting Started

1. Clone the repository
2. Set up Firebase credentials
3. Install dependencies
4. Run the application


## Next Tasks/Features
1. Create evaluation ROUGE notebook
2. Choose between multiple LLM's (OpenAI, Claude, Gemeni)
3. Handle generated content within RAG loop
