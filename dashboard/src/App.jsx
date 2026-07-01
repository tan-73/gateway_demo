import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";

const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";
const authHeaders = (token) => ({ Authorization: `Bearer ${token}`, "Content-Type": "application/json" });
const initialPlanForm = { name: "", rate_limit: 5, rate_window_secs: 60, credit_cost_multiplier: 1, renewal_frequency: "daily", base_credits: 20, valid_days: 30, active: true };
const initialKeyForm = { user_id: "", plan_id: "", active: true };

export function App() {
  const [loginMode, setLoginMode] = useState("admin");
  const [sessionMode, setSessionMode] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [adminEmail, setAdminEmail] = useState("admin@gateway-demo.local");
  const [adminPassword, setAdminPassword] = useState("demo-admin-pass");
  const [showPassword, setShowPassword] = useState(false);
  const [token, setToken] = useState("");
  const [role, setRole] = useState("");
  const [authMessage, setAuthMessage] = useState("");
  const [balance, setBalance] = useState(null);
  const [usage, setUsage] = useState([]);
  const [plans, setPlans] = useState([]);
  const [routes, setRoutes] = useState([]);
  const [keys, setKeys] = useState([]);
  const [users, setUsers] = useState([]);
  const [ledger, setLedger] = useState([]);
  const [logs, setLogs] = useState([]);
  const [catalogPreview, setCatalogPreview] = useState([]);
  const [recommendations, setRecommendations] = useState(null);
  const [productDetail, setProductDetail] = useState(null);
  const [inventory, setInventory] = useState(null);
  const [reviews, setReviews] = useState(null);
  const [productId, setProductId] = useState("sku-1");
  const [planForm, setPlanForm] = useState(initialPlanForm);
  const [keyForm, setKeyForm] = useState(initialKeyForm);
  const [createdApiKey, setCreatedApiKey] = useState("");

  async function login(event) {
    event.preventDefault();
    const endpoint = `${API_BASE}${loginMode === "admin" ? "/auth/admin-login" : "/auth/token"}`;
    const body = loginMode === "admin" ? { email: adminEmail, password: adminPassword } : { api_key: apiKey };
    const response = await fetch(endpoint, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    const data = await response.json();
    if (!response.ok) {
      setAuthMessage(data.detail ?? "Login failed");
      return;
    }
    setToken(data.access_token);
    setRole(data.role);
    setSessionMode(loginMode);
    setAuthMessage("");
  }

  useEffect(() => {
    if (!token) return;
    if (sessionMode === "consumer") {
      fetch(`${API_BASE}/me/credit-balance`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : null).then(setBalance);
      fetch(`${API_BASE}/me/usage`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : []).then(setUsage);
      fetch(`${API_BASE}/api/catalog/products`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : { items: [] }).then((data) => setCatalogPreview(data.items ?? []));
      fetch(`${API_BASE}/api/catalog/products/${productId}`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : { item: null }).then((data) => setProductDetail(data.item ?? null));
      fetch(`${API_BASE}/api/inventory/${productId}`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : { item: null }).then((data) => setInventory(data.item ?? null));
      fetch(`${API_BASE}/api/reviews/${productId}`, { headers: authHeaders(token) }).then((r) => r.ok ? r.json() : { items: [] }).then((data) => setReviews(data.items ?? []));
    } else {
      setBalance(null);
      setUsage([]);
      setCatalogPreview([]);
      setProductDetail(null);
      setInventory(null);
      setReviews([]);
    }
    if (role !== "developer") {
      fetch(`${API_BASE}/admin/plans`, { headers: authHeaders(token) }).then((r) => r.json()).then(setPlans);
      fetch(`${API_BASE}/admin/routes`, { headers: authHeaders(token) }).then((r) => r.json()).then(setRoutes);
      fetch(`${API_BASE}/admin/api-keys`, { headers: authHeaders(token) }).then((r) => r.json()).then(setKeys);
      fetch(`${API_BASE}/admin/users`, { headers: authHeaders(token) }).then((r) => r.json()).then(setUsers);
      fetch(`${API_BASE}/admin/credit-ledger`, { headers: authHeaders(token) }).then((r) => r.json()).then(setLedger);
      fetch(`${API_BASE}/admin/usage-logs`, { headers: authHeaders(token) }).then((r) => r.json()).then(setLogs);
    }
  }, [token, role, productId, sessionMode]);

  async function refreshBalance() {
    const response = await fetch(`${API_BASE}/me/credit-balance`, { headers: authHeaders(token) });
    if (response.ok) setBalance(await response.json());
  }

  async function refreshUsage() {
    const response = await fetch(`${API_BASE}/me/usage`, { headers: authHeaders(token) });
    if (response.ok) setUsage(await response.json());
  }

  async function fetchRecommendations() {
    const response = await fetch(`${API_BASE}/api/recommendations`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ customer_id: "demo-customer", cart: ["sku-1", "sku-3"], context: "homepage" }),
    });
    const data = await response.json();
    setRecommendations(data);
    await Promise.all([refreshBalance(), refreshUsage()]);
  }

  async function loadProductArtifacts() {
    const detail = await fetch(`${API_BASE}/api/catalog/products/${productId}`, { headers: authHeaders(token) }).then((r) => r.json());
    const stock = await fetch(`${API_BASE}/api/inventory/${productId}`, { headers: authHeaders(token) }).then((r) => r.json());
    const productReviews = await fetch(`${API_BASE}/api/reviews/${productId}`, { headers: authHeaders(token) }).then((r) => r.json());
    setProductDetail(detail.item ?? null);
    setInventory(stock.item ?? null);
    setReviews(productReviews.items ?? []);
    await Promise.all([refreshBalance(), refreshUsage()]);
  }

  async function createPlan(event) {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/admin/plans`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify(planForm),
    });
    const created = await response.json();
    setPlans((current) => [...current, created]);
    setPlanForm(initialPlanForm);
  }

  async function createApiKey(event) {
    event.preventDefault();
    const response = await fetch(`${API_BASE}/admin/api-keys`, {
      method: "POST",
      headers: authHeaders(token),
      body: JSON.stringify({ user_id: Number(keyForm.user_id), plan_id: Number(keyForm.plan_id), active: keyForm.active }),
    });
    const created = await response.json();
    if (response.ok) {
      setCreatedApiKey(created.api_key);
      setKeys((current) => [created.record, ...current]);
      setKeyForm(initialKeyForm);
    }
  }

  async function triggerRenewal() {
    await fetch(`${API_BASE}/admin/jobs/run-renewal`, { method: "POST", headers: authHeaders(token) });
    const refreshed = await fetch(`${API_BASE}/admin/credit-ledger`, { headers: authHeaders(token) }).then((r) => r.json());
    setLedger(refreshed);
  }

  function logout() {
    setToken("");
    setRole("");
    setSessionMode("");
    setBalance(null);
    setUsage([]);
    setRecommendations(null);
    setCreatedApiKey("");
  }

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <div className="mx-auto max-w-7xl p-6">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="text-sm uppercase tracking-[0.35em] text-cyan-300">Hosted Demo</div>
            <h1 className="mt-2 text-3xl font-semibold">Storefront API Gateway Demo</h1>
            <p className="mt-2 max-w-2xl text-sm text-slate-400">
              Demonstrates admin bootstrap, API-key issuance, live gateway policies, storefront REST calls, and premium metering in one UI.
            </p>
          </div>
          {token && <button onClick={logout} className="rounded-lg border border-slate-700 px-4 py-2 text-sm">Log Out</button>}
        </div>
        {!token ? (
          <div className="grid gap-6 lg:grid-cols-[1.2fr_0.8fr]">
            <form onSubmit={login} className="space-y-5 rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <div className="flex gap-2">
                <button type="button" onClick={() => setLoginMode("admin")} className={`rounded-lg px-4 py-2 text-sm ${loginMode === "admin" ? "bg-cyan-500 text-slate-950" : "border border-slate-700 text-slate-300"}`}>Admin Login</button>
                <button type="button" onClick={() => setLoginMode("consumer")} className={`rounded-lg px-4 py-2 text-sm ${loginMode === "consumer" ? "bg-cyan-500 text-slate-950" : "border border-slate-700 text-slate-300"}`}>Consumer API Key</button>
              </div>
              {loginMode === "admin" ? (
                <div className="grid gap-4 md:grid-cols-2">
                  <div>
                    <label className="mb-2 block text-sm text-slate-300">Admin Email</label>
                    <input className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" value={adminEmail} onChange={(e) => setAdminEmail(e.target.value)} />
                  </div>
                  <div>
                    <label className="mb-2 block text-sm text-slate-300">Admin Password</label>
                    <div className="flex gap-2">
                      <input type={showPassword ? "text" : "password"} className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" value={adminPassword} onChange={(e) => setAdminPassword(e.target.value)} />
                      <button type="button" onClick={() => setShowPassword((current) => !current)} className="rounded-lg border border-slate-700 px-3 py-2 text-sm text-slate-300">
                        {showPassword ? "Hide" : "Show"}
                      </button>
                    </div>
                  </div>
                </div>
              ) : (
                <div>
                  <label className="mb-2 block text-sm text-slate-300">Consumer API Key</label>
                  <input className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2" value={apiKey} onChange={(e) => setApiKey(e.target.value)} />
                </div>
              )}
              {authMessage && <div className="rounded-lg border border-rose-900 bg-rose-950/40 px-3 py-2 text-sm text-rose-200">{authMessage}</div>}
              <button className="rounded-lg bg-cyan-500 px-4 py-2 font-medium text-slate-950">{loginMode === "admin" ? "Enter Admin Console" : "Exchange API Key"}</button>
            </form>
            <div className="rounded-2xl border border-slate-800 bg-slate-900 p-6">
              <h2 className="text-xl font-medium">Demo Credentials</h2>
              <div className="mt-4 space-y-3 text-sm text-slate-300">
                <div className="rounded-lg border border-slate-800 p-3">
                  <div className="text-slate-400">Hosted admin login</div>
                  <div className="mt-1 font-mono">admin@gateway-demo.local</div>
                  <div className="font-mono">demo-admin-pass</div>
                </div>
                <div className="rounded-lg border border-slate-800 p-3">
                  <div className="text-slate-400">Consumer flow</div>
                  <div>Log in as admin first, create an API key for a developer, then switch to the consumer tab to exchange it for a JWT.</div>
                </div>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-6">
            <section className="grid gap-4 md:grid-cols-3">
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="text-sm text-slate-400">Role</div>
                <div className="mt-1 text-xl">{role}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="text-sm text-slate-400">{sessionMode === "admin" ? "Session" : "Credits"}</div>
                <div className="mt-1 text-xl">{sessionMode === "admin" ? "Admin Console" : (balance?.credit_balance ?? "-")}</div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="text-sm text-slate-400">{sessionMode === "admin" ? "Next Step" : "Plan"}</div>
                <div className="mt-1 text-xl">{sessionMode === "admin" ? "Issue Consumer Key" : (balance?.plan_name ?? "-")}</div>
              </div>
            </section>

            {sessionMode === "consumer" && (
              <>
                <section className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-medium">Catalog Preview</h2>
                  <span className="text-sm text-slate-400">Public storefront API</span>
                </div>
                <div className="space-y-2 text-sm">
                  {catalogPreview.map((item) => <div key={item.id} className="rounded-lg border border-slate-800 p-3">{item.name} · {item.category} · ${item.price}</div>)}
                </div>
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-medium">Gateway Explorer</h2>
                  <button onClick={loadProductArtifacts} className="rounded-lg border border-slate-700 px-3 py-2 text-sm">Refresh Calls</button>
                </div>
                <div className="mb-4 flex gap-2">
                  <input className="w-full rounded-lg border border-slate-700 bg-slate-950 px-3 py-2 text-sm" value={productId} onChange={(e) => setProductId(e.target.value)} />
                  <button onClick={loadProductArtifacts} className="rounded-lg bg-cyan-500 px-3 py-2 text-sm text-slate-950">Fetch</button>
                </div>
                <div className="space-y-3 text-sm">
                  <div className="rounded-lg border border-slate-800 p-3">
                    <div className="text-slate-400">Product</div>
                    <div className="mt-1">{productDetail ? `${productDetail.name} · $${productDetail.price}` : "No result"}</div>
                  </div>
                  <div className="rounded-lg border border-slate-800 p-3">
                    <div className="text-slate-400">Inventory</div>
                    <div className="mt-1">{inventory ? `${inventory.available} units in ${inventory.warehouse}` : "No result"}</div>
                  </div>
                  <div className="rounded-lg border border-slate-800 p-3">
                    <div className="text-slate-400">Reviews</div>
                    <div className="mt-1">{reviews?.length ? reviews.map((item) => `${item.author}: ${item.headline}`).join(" | ") : "No reviews loaded"}</div>
                  </div>
                </div>
              </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <div className="mb-4 flex items-center justify-between">
                  <h2 className="text-xl font-medium">Premium Recommendations</h2>
                  <button onClick={fetchRecommendations} className="rounded-lg bg-cyan-500 px-3 py-2 text-slate-950">Run Premium Call</button>
                </div>
                {recommendations ? (
                  <div className="space-y-2 text-sm">
                    {recommendations.suggestions.map((item) => <div key={item.product_id} className="rounded-lg border border-slate-800 p-3">{item.product_id} · {item.reason}</div>)}
                  </div>
                ) : (
                  <div className="text-sm text-slate-400">Use the premium API to see recommendation results and credit usage.</div>
                )}
              </div>
              <div className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                <h2 className="mb-4 text-xl font-medium">Recent Usage</h2>
                <div className="h-64">
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={usage.slice(0, 10)}>
                      <XAxis dataKey="id" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="credits_charged" fill="#06b6d4" />
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </div>
            </section>
              </>
            )}

            {sessionMode === "admin" && (
              <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4 text-sm text-slate-300">
                <h2 className="text-xl font-medium">Admin Demonstration Flow</h2>
                <p className="mt-3">Use the forms below to create a consumer API key. Then copy the raw key shown once, log out, switch to the consumer tab, and exchange that key for a JWT to exercise the gateway storefront APIs.</p>
              </section>
            )}

            {role !== "developer" && (
              <div className="grid gap-6 lg:grid-cols-2">
                <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                  <div className="mb-4 flex items-center justify-between">
                    <h2 className="text-xl font-medium">Plans</h2>
                    <button onClick={triggerRenewal} className="rounded-lg bg-amber-400 px-3 py-2 text-slate-950">Run Renewal</button>
                  </div>
                  <form onSubmit={createPlan} className="mb-4 grid gap-2 md:grid-cols-2">
                    <input className="rounded bg-slate-950 p-2" placeholder="Plan name" value={planForm.name} onChange={(e) => setPlanForm({ ...planForm, name: e.target.value })} />
                    <input className="rounded bg-slate-950 p-2" type="number" placeholder="Rate limit" value={planForm.rate_limit} onChange={(e) => setPlanForm({ ...planForm, rate_limit: Number(e.target.value) })} />
                    <input className="rounded bg-slate-950 p-2" type="number" placeholder="Window seconds" value={planForm.rate_window_secs} onChange={(e) => setPlanForm({ ...planForm, rate_window_secs: Number(e.target.value) })} />
                    <input className="rounded bg-slate-950 p-2" type="number" step="0.1" placeholder="Multiplier" value={planForm.credit_cost_multiplier} onChange={(e) => setPlanForm({ ...planForm, credit_cost_multiplier: Number(e.target.value) })} />
                    <input className="rounded bg-slate-950 p-2" type="number" placeholder="Credits" value={planForm.base_credits} onChange={(e) => setPlanForm({ ...planForm, base_credits: Number(e.target.value) })} />
                    <input className="rounded bg-slate-950 p-2" type="number" placeholder="Valid days" value={planForm.valid_days} onChange={(e) => setPlanForm({ ...planForm, valid_days: Number(e.target.value) })} />
                    <button className="rounded bg-cyan-500 px-4 py-2 font-medium text-slate-950">Create Plan</button>
                  </form>
                  <div className="space-y-2 text-sm">
                    {plans.map((plan) => <div key={plan.id} className="rounded-lg border border-slate-800 p-3">{plan.name} · limit {plan.rate_limit}/{plan.rate_window_secs}s · credits {plan.base_credits}</div>)}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                  <h2 className="mb-4 text-xl font-medium">Routes</h2>
                  <div className="space-y-2 text-sm">
                    {routes.map((route) => <div key={route.id} className="rounded-lg border border-slate-800 p-3">{route.method} {route.path_pattern} · {route.category} tier · cost {route.base_credit_cost}</div>)}
                  </div>
                  <h2 className="mb-4 mt-6 text-xl font-medium">API Keys</h2>
                  <form onSubmit={createApiKey} className="mb-4 grid gap-2 md:grid-cols-2">
                    <select className="rounded bg-slate-950 p-2" value={keyForm.user_id} onChange={(e) => setKeyForm({ ...keyForm, user_id: e.target.value })}>
                      <option value="">Select user</option>
                      {users.map((user) => <option key={user.id} value={user.id}>{user.email}</option>)}
                    </select>
                    <select className="rounded bg-slate-950 p-2" value={keyForm.plan_id} onChange={(e) => setKeyForm({ ...keyForm, plan_id: e.target.value })}>
                      <option value="">Select plan</option>
                      {plans.map((plan) => <option key={plan.id} value={plan.id}>{plan.name}</option>)}
                    </select>
                    <button className="rounded bg-emerald-400 px-4 py-2 font-medium text-slate-950">Create API Key</button>
                  </form>
                  {createdApiKey && <div className="mb-4 rounded-lg border border-emerald-800 bg-emerald-950/40 p-3 text-sm text-emerald-200">Raw API key shown once: <span className="font-mono">{createdApiKey}</span></div>}
                  <div className="space-y-2 text-sm">
                    {keys.map((key) => <div key={key.id} className="rounded-lg border border-slate-800 p-3">Key #{key.id} · balance {key.credit_balance} · active {String(key.active)}</div>)}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                  <h2 className="mb-4 text-xl font-medium">Usage Logs</h2>
                  <div className="max-h-80 space-y-2 overflow-auto text-sm">
                    {logs.map((log) => <div key={log.id} className="rounded-lg border border-slate-800 p-3">Route {log.route_id} · status {log.status_code} · {Math.round(log.latency_ms)}ms · charged {log.credits_charged}</div>)}
                  </div>
                </section>

                <section className="rounded-2xl border border-slate-800 bg-slate-900 p-4">
                  <h2 className="mb-4 text-xl font-medium">Credit Ledger</h2>
                  <div className="max-h-80 space-y-2 overflow-auto text-sm">
                    {ledger.map((item) => <div key={item.id} className="rounded-lg border border-slate-800 p-3">Key {item.api_key_id} · {item.reason} · {item.delta} → {item.balance_after}</div>)}
                  </div>
                </section>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
