import { createClient } from '@supabase/supabase-js'

const supabaseUrl = import.meta.env.VITE_SUPABASE_URL
const supabaseAnonKey = import.meta.env.VITE_SUPABASE_ANON_KEY

// In dev, if env vars are missing, export a safe no-op client
// so the app can run without Supabase.
function makeThenable(result) {
  return {
    order() { return makeThenable(result); },
    select() { return makeThenable(result); },
    insert() { return makeThenable({ data: null, error: null }); },
    single() { return makeThenable(result); },
    limit() { return makeThenable(result); },
    then(onFulfilled) { return Promise.resolve(result).then(onFulfilled); },
  };
}

export const supabase = (supabaseUrl && supabaseAnonKey)
  ? createClient(supabaseUrl, supabaseAnonKey)
  : {
      from() {
        const res = { data: [], error: null };
        return {
          select() { return makeThenable(res); },
          insert() { return makeThenable({ data: null, error: null }); },
          order() { return makeThenable(res); },
          limit() { return makeThenable(res); },
          then(onFulfilled) { return Promise.resolve(res).then(onFulfilled); },
        };
      },
    };