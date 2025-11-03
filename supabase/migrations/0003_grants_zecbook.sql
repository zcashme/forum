-- Grants for access via PostgREST and service role writes

-- Explicitly grant USAGE on schema to each role
GRANT USAGE ON SCHEMA zda TO service_role;
GRANT USAGE ON SCHEMA zda TO anon;
GRANT USAGE ON SCHEMA zda TO authenticated;

-- Read access on the public view (avoid schema dot by setting search_path)
SET search_path = public;
GRANT SELECT ON zecbook TO anon;
GRANT SELECT ON zecbook TO authenticated;

-- Write access for service role on base table and its sequence
SET search_path = zda;
GRANT INSERT ON zecbook TO service_role;
GRANT UPDATE ON zecbook TO service_role;
GRANT DELETE ON zecbook TO service_role;
GRANT USAGE ON SEQUENCE zecbook_id_seq TO service_role;
GRANT SELECT ON SEQUENCE zecbook_id_seq TO service_role;