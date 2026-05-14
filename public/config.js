// Client-side configuration. The publishable key is safe to ship in
// the bundle — every privileged operation is gated by RLS / RPCs on
// the Supabase side. Rotate via the Supabase dashboard if needed.
window.TASUKETE_CONFIG = {
  supabaseUrl:    'https://bxewkghaljeucxekwltd.supabase.co',
  supabaseAnonKey:'sb_publishable_SqNDIE4ajCb303rezbUcnQ_t9tQfONS',
  // The schema all our tables and RPCs live in.
  schema:         'tasukete',
  // Default radius (in metres) for the nearby feed.
  defaultRadiusM: 2000,
};
