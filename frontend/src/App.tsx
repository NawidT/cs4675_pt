import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import { createContext, useState } from 'react';

// create a context to store the user's first name and last name
export const UserContext = createContext({
  userfname: '',
  userlname: '',
  setUserfname: (fname: string) => {},
  setUserlname: (lname: string) => {},
  human_messages: [] as string[],
  ai_responses: [] as string[],
  setHumanMessages: (messages: string[]) => {},
  setAiResponses: (responses: string[]) => {},
  meal_plan: '' as string,
  setMealPlan: (plan: string) => {},
});

// Create a theme instance
const theme = createTheme({
  palette: {
    primary: {
      main: '#2196f3',
    },
    secondary: {
      main: '#f50057',
    },
  },
});

function App() {
  const [userfname, setUserfname] = useState('');
  const [userlname, setUserlname] = useState(''); 
  const [human_messages, setHumanMessages] = useState<string[]>([]);
  const [ai_responses, setAiResponses] = useState<string[]>([]);
  const [meal_plan, setMealPlan] = useState<string>('');
  return (  
    <ThemeProvider theme={theme}>
      <UserContext.Provider value={{ userfname, userlname, setUserfname, setUserlname, 
        human_messages, ai_responses, setHumanMessages, setAiResponses, meal_plan, setMealPlan}}>
        <Router>
          <Routes>
            <Route path="/" element={<LandingPage />} />
          <Route path="/chat" element={<ChatPage />} />
          </Routes>
        </Router>
      </UserContext.Provider>
    </ThemeProvider>
  );
}

export default App;
