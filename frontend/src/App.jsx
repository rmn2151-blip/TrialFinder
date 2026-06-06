import { Routes, Route } from "react-router-dom";
import Header from "./components/Header.jsx";
import Home from "./pages/Home.jsx";
import Results from "./pages/Results.jsx";
import Login from "./pages/Login.jsx";
import Watchlist from "./pages/Watchlist.jsx";
import WhatIsTrial from "./pages/WhatIsTrial.jsx";
import WhyParticipate from "./pages/WhyParticipate.jsx";

export default function App() {
  return (
    <div className="app">
      <Header />
      <main id="main-content">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/results" element={<Results />} />
          <Route path="/login" element={<Login />} />
          <Route path="/watchlist" element={<Watchlist />} />
          <Route path="/what-is-a-clinical-trial" element={<WhatIsTrial />} />
          <Route path="/why-participate" element={<WhyParticipate />} />
        </Routes>
      </main>
    </div>
  );
}
