import "./index.css";
import { Routes, Route, useNavigate } from "react-router-dom";
import { useState, useEffect } from "react";
import Directory from "./Directory";
import { FeedbackProvider } from "./store";
import LatestMessages from "./LatestMessages";
import Authenticate from "./Authenticate";
import AccountTransactions from "./AccountTransactions";
import AnonymousBoard from "./AnonymousBoard";

function App() {
  const [searchQuery, setSearchQuery] = useState("");
  const navigate = useNavigate();

  // 🧠 When user types in search bar, go back to the main directory view
  useEffect(() => {
    if (searchQuery.trim() !== "") {
      navigate("/"); // ensures the directory view shows
    }
  }, [searchQuery, navigate]);

  return (
    <FeedbackProvider>
      <Routes>
        {/* Wildcard route: handles / and all slugs */}
        <Route
          path="/*"
          element={
            <Directory
              searchQuery={searchQuery}
              onSearchChange={setSearchQuery}
            />
          }
        />
        <Route path="/messages" element={<LatestMessages />} />
        <Route path="/board" element={<AnonymousBoard />} />
        <Route path="/auth" element={<Authenticate />} />
        <Route path="/tx" element={<AccountTransactions />} />
      </Routes>
    </FeedbackProvider>
  );
}

export default App;
