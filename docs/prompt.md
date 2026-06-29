hi, i want to change my agent team Linus and Grace,
Linus was sonnet model
Grace was queen2.5 on my mac os,

now i want to change all the configureing like start we start again,

Act as an expert Senior AI Solutions Architect specializing in LangGraph, Multi-Agent Systems, and Advanced RAG architectures.

I am building a completely autonomous E-commerce Multi-Agent System that connects to the CJ Dropshipping API to source products and automatically deploys them onto a Shopify store via Shopify's GraphQL API. The system must also handle content generation, UX design alignment, and initial marketing campaign setup.

Please design the complete architecture, define the state, and scaffold the Python LangGraph code based on the exact specifications below.

---

### 1. THE AGENT TEAM & ROLES

I need a workflow comprising the following 5 distinct agent nodes controlled by a central orchestrator:

1. **Agent CEO (Orchestrator & Router):**
   - Act as the central brain. Receives the initial high-level command (e.g., "Find and launch 3 trending kitchen products").
   - Manages the global state, routes tasks to the specific agents sequentially, and evaluates execution.
   - Triggers Slack alerts for human-in-the-loop approvals at critical stages.

2. **Agent Product Hunter (Market Analyst):**
   - Connects directly to the CJ Dropshipping API.
   - Sources trending products filtering by criteria: High product rating, reliable shipping times to target destinations, and verified minimum inventory levels.
   - For every candidate, it queries live competitor prices using web search tools (e.g., Tavily/Perplexity) to calculate potential profitability.
   - Incorporates a strict 18% VAT and standard payment processing fees into the mathematical cost model to ensure accurate margin calculations.

3. **Agent UX & Content (Copywriter & Brand Designer):**
   - Extracts the raw, often unoptimized product descriptions and data sheets provided by the CJ API.
   - Refines and rewrites high-converting, localized marketing copy tailored to the target audience.
   - Ensures all copywriting and visual requests strictly respect a pre-defined brand style kit (injecting explicit hexadecimal brand colors and cohesive typography rules into its context).

4. **Agent Shopify Developer (Technical Infrastructure):**
   - Consumes the finalized, validated product data, images, and marketing copy from the state.
   - Authenticates and pushes the payload directly to the Shopify store using the Shopify GraphQL API.
   - Sets up product tags, technical SEO metadata, collections, and variants.

5. **Agent Growth Marketer (PPC & Traffic):**
   - Prepares the launch blueprint for ad campaigns.
   - Generates ad copies, hooks, and targeting strategies for social channels based on the product's winning angles.

---

### 2. AGENTIC RAG WORKFLOW (REASONING & SELF-CORRECTION)

The Product Hunter must not just pull data blindly; it must run an Agentic RAG cycle with self-correction capabilities implemented via an "Evaluator Node":

- **Retrieve:** Fetch product listings from CJ Dropshipping API + competitor pricing from Vector DB/Search Tools.
- **Reason & Calculate:** Execute mathematical calculation of the net profit margin (including the 18% VAT and shipping costs).
- **Evaluate (Self-Correction Loop):** If the calculated profit margin falls below our target threshold, the Evaluator Node rejects the state, increments a `loop_counter`, and routes the flow back to the Product Hunter to adjust criteria or fetch a different product cluster.
- **Guardrails:** To prevent infinite token burn or endless execution loops, implement a hard cap of `max_loops=3`. If reached, it routes to a "Failed" node and triggers a Slack notification for human intervention.

---

### 3. EXPECTED CODE ARCHITECTURE

Please generate the Python code scaffolding using `langgraph` and `pydantic`. The code must include:

1. **`State` Class (TypedDict/Pydantic):** To track messages, extracted product data, pricing calculations, loop counters, and overall workflow status.
2. **Node Functions:** Stub functions for `ceo_node`, `product_hunter_node`, `evaluator_node`, `ux_content_node`, `shopify_dev_node`, and `marketer_node`.
3. **Graph Definition:** Building the `StateGraph`, adding nodes, defining conditional edges (especially the self-correction logic from the evaluator), and compiling it.

Let's write this modularly. Start by sketching out the full architecture and then provide the Python code for the graph definition.

also we have this platform-app that contain all of the ideas how the system will works
http://localhost:5173/

we have dbs and agents permissions
you need to update the agents that work now on the project.

we need to also to check every time how much we have in
https://platform.claude.com/dashboard
to spend $ and use it until start month (1 of every month),
so i will add more 100$ every start month until 1 and again

so now the agents can spend $39.42 until start month 1 of Jul,

i add application to the store like CJ dropshipping and Facebook & Instegram to create Ads to my products

now the products have to update by agents all needs to get from CJ they have permission from config

the agents can talk with me on SLACK and show what they doing and meeting

we have only 1 store live the domain is timeofbaby.alpha-tech.live DNS from our cloudflare
the files of the store /Users/itziksavaia/Documents/git/alpha-shoop/stores/shopify/timeofbaby.alpha-tech.live

is like template if we need to create more shopify stores so on this path
/Users/itziksavaia/Documents/git/alpha-shoop/stores/shopify copy the timeofbaby.alpha-tech.live stucture like a template
if outer stores /Users/itziksavaia/Documents/git/alpha-shoop/stores create new folder like ebay now is not relevant!

you need to add claude.md under the store folder to explain how to work in this store
for shopify stores you need to add changelog + timestemp title context, and readme of the store
every change on the store is need to be in changelog and if is change is imported add it to readme

one more think go through all the files and folders and see if I'm using them. If not, delete and update git.
