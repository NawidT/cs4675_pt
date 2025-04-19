import { Box, Button, Typography, Container, Dialog, DialogTitle, DialogContent, TextField, DialogActions } from '@mui/material';
import { useNavigate } from 'react-router-dom';
import { useContext, useState } from 'react';
import { UserContext } from '../App';

const LandingPage = () => {
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [firstName, setFirstName] = useState('');
  const [lastName, setLastName] = useState('');
  const { setUserfname, setUserlname, setHumanMessages, setAiResponses, setMealPlan } = useContext(UserContext);

  const handleClickOpen = () => {
    setOpen(true);
  };

  const handleClose = () => {
    setOpen(false);
  };

  const handleSubmit = async () => {
    if (firstName.trim() && lastName.trim()) {
      // call localhost:5000/init with firstName and lastName
      const response = await fetch('https://cs4675pt-production.up.railway.app/init', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          userfname: firstName,
          userlname: lastName,
        }),
      });
      const data = await response.json();
      if (data.status === 'success') {
        setUserfname(firstName);
        setUserlname(lastName);
        setHumanMessages(data.human_messages);
        setAiResponses(data.ai_responses);
        setMealPlan(data.meal_plan);
        navigate('/chat');
      } else {
        console.error('Failed to initialize user');
      }
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        width: '100vw',
        display: 'flex',
        flexDirection: 'column',
        background: 'linear-gradient(135deg, #1a237e 0%, #0d47a1 100%)',
        color: 'white',
        position: 'relative',
        overflow: 'hidden',
      }}
    >
      {/* Background Pattern */}
      <Box
        sx={{
          position: 'absolute',
          top: 0,
          left: 0,
          right: 0,
          bottom: 0,
          backgroundImage: 'radial-gradient(circle at 1px 1px, rgba(255,255,255,0.1) 1px, transparent 0)',
          backgroundSize: '40px 40px',
          opacity: 0.1,
        }}
      />

      {/* Content */}
      <Container
        maxWidth="lg"
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
          alignItems: 'center',
          position: 'relative',
          zIndex: 1,
          textAlign: 'center',
          py: 8,
        }}
      >
        {/* Main Title */}
        <Typography
          variant="h1"
          component="h1"
          sx={{
            fontSize: { xs: '2.5rem', md: '4rem' },
            fontWeight: 800,
            mb: 2,
            background: 'linear-gradient(45deg, #fff 30%, #e3f2fd 90%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            textShadow: '2px 2px 4px rgba(0,0,0,0.1)',
          }}
        >
          PT (Personal Transformer)
        </Typography>

        {/* Subtitle */}
        <Typography
          variant="h4"
          sx={{
            mb: 4,
            color: 'rgba(255,255,255,0.9)',
            maxWidth: '800px',
            lineHeight: 1.6,
          }}
        >
          Your AI-powered personal nutrition and fitness assistant
        </Typography>

        {/* Description */}
        <Typography
          variant="h6"
          sx={{
            mb: 6,
            color: 'rgba(255,255,255,0.8)',
            maxWidth: '600px',
            lineHeight: 1.8,
          }}
        >
          Get personalized meal plans and nutritional advice tailored to your specific needs.
          Our AI assistant learns from your preferences and provides continuous guidance
          to help you achieve your health goals.
        </Typography>

        {/* Features Grid */}
        <Box
          sx={{
            display: 'grid',
            gridTemplateColumns: { xs: '1fr', md: 'repeat(3, 1fr)' },
            gap: 4,
            mb: 6,
            width: '100%',
            maxWidth: '1000px',
          }}
        >
          {[
            {
              title: 'Personalized Plans',
              description: 'Custom meal and fitness plans based on your goals and preferences',
            },
            {
              title: 'AI-Powered Guidance',
              description: 'Smart recommendations that adapt to your progress and feedback',
            },
            {
              title: 'Continuous Support',
              description: '24/7 access to nutritional advice and progress tracking',
            },
          ].map((feature, index) => (
            <Box
              key={index}
              sx={{
                p: 3,
                borderRadius: 2,
                bgcolor: 'rgba(255,255,255,0.1)',
                backdropFilter: 'blur(10px)',
                border: '1px solid rgba(255,255,255,0.2)',
                transition: 'transform 0.2s',
                '&:hover': {
                  transform: 'translateY(-5px)',
                },
              }}
            >
              <Typography variant="h6" sx={{ mb: 2, fontWeight: 600 }}>
                {feature.title}
              </Typography>
              <Typography sx={{ color: 'rgba(255,255,255,0.8)' }}>
                {feature.description}
              </Typography>
            </Box>
          ))}
        </Box>

        {/* CTA Button */}
        <Button
          variant="contained"
          size="large"
          onClick={handleClickOpen}
          sx={{
            py: 2,
            px: 6,
            fontSize: '1.2rem',
            borderRadius: 3,
            background: 'linear-gradient(45deg, #2196f3 30%, #21cbf3 90%)',
            boxShadow: '0 3px 5px 2px rgba(33, 203, 243, .3)',
            '&:hover': {
              background: 'linear-gradient(45deg, #1976d2 30%, #1cb5e0 90%)',
            },
          }}
        >
          Start Your Journey
        </Button>

        {/* User Information Dialog */}
        <Dialog open={open} onClose={handleClose}>
          <DialogTitle>Before we begin...</DialogTitle>
          <DialogContent>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2, pt: 2 }}>
              <TextField
                autoFocus
                label="First Name"
                fullWidth
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
              />
              <TextField
                label="Last Name"
                fullWidth
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
              />
            </Box>
          </DialogContent>
          <DialogActions>
            <Button onClick={handleClose}>Cancel</Button>
            <Button 
              onClick={handleSubmit}
              disabled={!firstName.trim() || !lastName.trim()}
            >
              Continue
            </Button>
          </DialogActions>
        </Dialog>
      </Container>
    </Box>
  );
};

export default LandingPage; 