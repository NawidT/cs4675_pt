import { BrowserRouter as Router, Routes, Route } from 'react-router-dom';
import { ThemeProvider, createTheme } from '@mui/material';
import LandingPage from './pages/LandingPage';
import ChatPage from './pages/ChatPage';
import { createContext, useState } from 'react';

interface UserContextType {
  userfname: string;
  userlname: string;
  setUserfname: (fname: string) => void;
  setUserlname: (lname: string) => void;
  human_messages: string[];
  ai_responses: string[];
  setHumanMessages: (messages: string[]) => void;
  setAiResponses: (responses: string[]) => void;
  meal_plan: string;
  setMealPlan: (plan: string) => void;
}

// create a context to store the user's first name and last name
export const UserContext = createContext<UserContextType>({
  userfname: '',
  userlname: '',
  setUserfname: () => {},
  setUserlname: () => {},
  human_messages: [],
  ai_responses: [],
  setHumanMessages: () => {},
  setAiResponses: () => {},
  meal_plan: '',
  setMealPlan: () => {},
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
