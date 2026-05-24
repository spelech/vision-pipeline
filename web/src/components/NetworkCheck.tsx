import { useEffect } from 'react';

export function NetworkCheck() {
  useEffect(() => {
    // Simple connection check to backend when app loads
    fetch('/api/config')
      .then(res => {
        if (!res.ok) {
          console.error("Connection check failed with status:", res.status);
        } else {
          console.log("Connection check successful");
        }
      })
      .catch(err => {
         console.error("Connection check failed completely:", err);
      });
  }, []);
  
  return null;
}
