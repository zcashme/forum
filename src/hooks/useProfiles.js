import { useEffect, useState } from "react";
import { supabase } from "../supabase";

let cachedProfiles = null; // memory cache

export default function useProfiles() {
  const [profiles, setProfiles] = useState(cachedProfiles || []);
  const [loading, setLoading] = useState(!cachedProfiles);

  useEffect(() => {
    if (cachedProfiles) return; // already cached, skip fetch

    let active = true;
    setLoading(true);

    (async () => {
      try {
        const { data, error } = await supabase
          .from("zcasher_with_referral_rank")
          .select("*, links:zcasher_links(id, label, url, is_verified, created_at)")
          .order("name", { ascending: true });

        if (!active) return;
        if (error) {
          // Graceful fallback when table/view is not present
          const code = error.code || "";
          if (code === "PGRST205") {
            console.warn(
              "[Directory] profiles dataset not configured (missing zcasher_with_referral_rank). Showing empty list."
            );
            cachedProfiles = [];
            setProfiles([]);
          } else {
            console.warn("[Directory] failed to load profiles:", error.message || error);
            cachedProfiles = [];
            setProfiles([]);
          }
        } else {
          cachedProfiles = Array.isArray(data) ? data : [];
          setProfiles(cachedProfiles);
        }
      } catch (e) {
        if (!active) return;
        console.warn("[Directory] unexpected error while loading profiles:", e?.message || e);
        cachedProfiles = [];
        setProfiles([]);
      } finally {
        if (active) setLoading(false);
      }
    })();

    return () => {
      active = false;
    };
  }, []);

  return { profiles, loading };
}
