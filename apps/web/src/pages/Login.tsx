import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ShieldAlert } from 'lucide-react';

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');

  const handleLogin = (e: React.FormEvent) => {
    e.preventDefault();
    if (username === 'Mahamed97' && password === 'Admin1234') {
      localStorage.setItem('auth', 'true');
      navigate('/');
    } else {
      setError('ACCESS DENIED: Invalid credentials');
    }
  };

  return (
    <div className="min-h-screen bg-[#0e0e0e] text-[#e5e2e1] flex items-center justify-center p-4 font-sans">
      <div className="w-full max-w-md bg-[#1c1b1b] border border-[#353534] p-8 shadow-2xl relative overflow-hidden">
        {/* Decorative corner brackets for industrial feel */}
        <div className="absolute top-0 left-0 w-8 h-8 border-t-2 border-l-2 border-[#00e5ff]/30 m-4" />
        <div className="absolute top-0 right-0 w-8 h-8 border-t-2 border-r-2 border-[#00e5ff]/30 m-4" />
        <div className="absolute bottom-0 left-0 w-8 h-8 border-b-2 border-l-2 border-[#00e5ff]/30 m-4" />
        <div className="absolute bottom-0 right-0 w-8 h-8 border-b-2 border-r-2 border-[#00e5ff]/30 m-4" />

        <div className="flex flex-col items-center mb-8">
          <ShieldAlert size={48} className="text-[#00e5ff] mb-4" />
          <h1 className="text-2xl font-bold tracking-widest text-center">FARM-PLC <br/> <span className="text-[#00e5ff]">HMI TERMINAL</span></h1>
          <p className="text-sm text-[#849396] mt-2 font-mono">SECURE AUTHENTICATION REQUIRED</p>
        </div>

        {error && (
          <div className="mb-6 p-3 bg-[#ffb4ab]/10 border border-[#ffb4ab] text-[#ffb4ab] text-sm font-mono text-center">
            {error}
          </div>
        )}

        <form onSubmit={handleLogin} className="space-y-6 relative z-10">
          <div>
            <label className="block text-xs font-bold text-[#bac9cc] mb-2 tracking-widest font-mono">
              [OPERATOR ID]
            </label>
            <input
              type="text"
              className="w-full bg-[#0e0e0e] border border-[#353534] p-3 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff] transition-colors font-mono"
              placeholder="Enter ID"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
            />
          </div>

          <div>
            <label className="block text-xs font-bold text-[#bac9cc] mb-2 tracking-widest font-mono">
              [PASSCODE]
            </label>
            <input
              type="password"
              className="w-full bg-[#0e0e0e] border border-[#353534] p-3 text-[#e5e2e1] focus:outline-none focus:border-[#00e5ff] transition-colors font-mono"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <button
            type="submit"
            className="w-full bg-[#00e5ff] hover:bg-[#00c9e0] text-[#0e0e0e] font-bold py-3 uppercase tracking-widest transition-colors font-mono mt-4"
          >
            AUTHORIZE & CONNECT
          </button>
        </form>

        <div className="mt-8 pt-4 border-t border-[#353534] text-center">
          <p className="text-xs text-[#849396] font-mono">SYS.VERSION 1.0.0-MVP</p>
        </div>
      </div>
    </div>
  );
}
