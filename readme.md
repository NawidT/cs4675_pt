# Personal Transformer (PT) 🏋️‍♂️

Personal Transformer (PT) is an intelligent fitness companion that leverages RAG (Retrieval-Augmented Generation) technology to provide personalized fitness guidance and maintain ongoing conversations about your health journey.

## Features

- **Personalized Fitness Chat**: Engage in natural conversations about your fitness goals, routines, and progress
- **Long-term Memory**: Maintains context of your previous conversations and fitness journey
- **Firebase Integration**: Secure storage of user data and chat history
- **RAG Technology**: Combines knowledge retrieval with conversational AI for accurate, contextual responses
- **Progress Tracking**: Keep track of your fitness milestones and achievements

## Technical Stack

- Langchain for Ease of AI interactions: https://www.langchain.com
- Firebase Realtime Database for RAG (Retrieval-Augmented Generation)
- Flask to run our Python API
- React.js as our frontend framework
- Vercel to host our frontend on https://cs4675pt.vercel.app/
- Railway to host our backend and handle CI/CD automatically

## System Design Overview
![Draw.io for the System Design](https://github.com/NawidT/cs4675_pt/blob/main/assets/system_design.png)
- For a more detailed walkthrough of the code view the report.

## The code is deployed virtually at https://cs4675pt.vercel.app

## Running the code locally:
1. Clone the repository
2. Set up Firebase credentials and environment variables
3. Inside LandingPage.tsx and ChatPage.tsx change the server_url variable to "http://localhost:5000"
4. To run the server
     - Open a separate console
       ```bash
       cd backend/
       pip install -r requirements.txt
       python main.py
       ```
5. To run the UI
     - Open a separate console
       ```bash
       cd frontend/
       npm install
       npm run dev
       ```
6. Visit http://localhost:5173/ in your browser to open the application

## Next Tasks/Features
1. Create evaluation ROUGE notebook
2. Integrate reinforcement learning human feedback (RLHF) to select best models from the batch
3. Integrate open-source models into the backend server
