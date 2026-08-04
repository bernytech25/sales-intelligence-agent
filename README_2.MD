# AI Solution Specialist — Written Assessment Responses

**1 - What is the most impactful AI solution you have personally built? Please briefly describe the problem, your role, the technologies used, and the business outcome.**

The most significant solution I have developed is a **Sales Intelligence Agent**: a conversational agent designed to analyze sales data using natural language, as an alternative to static dashboards and manual SQL queries. The underlying problem is a common one in organizations with sales data: the information exists, but extracting insights from it typically depends on personnel with specific technical skills, which introduces delays and creates a dependency on third parties for decisions that require agility.

I was solely responsible for the design and development of the project, end to end. I built two architecturally equivalent variants in order to compare them directly: one based on **LangGraph with Groq** (using the `llama-3.3-70b-versatile` model) and another based on **Semantic Kernel with Azure OpenAI** (`gpt-4o`). A core design decision was to fully decouple the business logic from the orchestration layer, through a set of 9 Pandas-based tool functions implemented in an independent module. This allowed both frameworks to operate on exactly the same underlying logic without duplication or modification, enabling an objective comparison in terms of performance, observability, and maintainability.

The solution includes a REST API built with FastAPI (6 endpoints), a two-layer persistent memory system (in-session memory and cross-session memory, currently being migrated to Azure Cosmos DB), Docker containerization, deployment on Azure Container Apps, continuous integration via GitHub Actions, and observability through LangSmith. I also built a test suite of 37 automated tests (unit and integration) to ensure the reliability of the business logic.

As a result, the project delivered a functional tool that allows non-technical users to ask natural language questions about sales data and receive accurate, data-grounded answers. From a professional standpoint, the project allowed me to demonstrate competencies in AI agent architecture, multi-provider integration (Groq and Azure), and software engineering best practices applied to AI systems, including testing, CI/CD, and observability.

---

**2 - Describe a workflow, process, or decision-making task that you successfully automated using AI. What systems were involved, and what part did you personally design or build?**

Within the same project, I automated the process of **sales data analysis for business decision-making**. Previously, this type of task required a technical resource to write a query, run it, and translate the results into a format understandable to whoever needed to make the decision. I designed a system in which that entire cycle — interpreting the natural language question, reasoning about it, executing the corresponding operation on the data, and generating an interpreted response — happens autonomously in a single interaction.

The systems involved were: an agent orchestrator (LangGraph or Semantic Kernel, depending on the variant), a language model (Groq or Azure OpenAI) responsible for interpreting user intent and selecting the appropriate tool, and a set of Pandas-based data analysis functions that I designed specifically to cover the most common business queries (sales by period, top-selling products, comparisons, trends, among others).

My responsibility covered both the design of the agent's decision-making logic and the development of the underlying business functions, as well as resolving real-world production issues. These included replacing models that were deprecated mid-development, adjusting Azure quotas due to regional availability limitations, and handling a security incident caused by accidentally exposed credentials, which was flagged by GitHub's push protection — this led me to conduct a full review of secrets management in the CI/CD pipeline.

As a result, the time between formulating a business question and obtaining an actionable answer was significantly reduced, eliminating the need for technical intervention in between.

---

**3 - Many business processes involve large volumes of documents, records, communications, and structured data. If you were asked to improve one of these processes using AI, how would you approach identifying opportunities and designing a solution?**

My approach follows three stages: understanding the data and the underlying business problem, designing with decoupling in mind, and validating early through a functional prototype.

First, before evaluating any technology, I would identify precisely where the inefficiency lies: whether it is a **retrieval problem** — information scattered across different systems or formats — or a **reasoning problem**, once the information is already available. These are fundamentally different problems that call for different architectures. This distinction comes from my experience building, in parallel, a semantic document retrieval system based on RAG with FAISS, and the Sales Intelligence Agent, focused on reasoning over structured data.

Second, I would design the solution by prioritizing decoupling between business logic and the AI layer, following the same principle applied in the Sales Intelligence Agent. This approach has two key advantages: it allows the business logic to be tested in isolation and reliably, without depending on the non-deterministic nature of a language model; and it makes it easier to swap AI providers or orchestration frameworks without rewriting the core of the system — particularly relevant given how quickly this technology ecosystem evolves.

Third, I would build a functional prototype as quickly as possible, using real data from the process in question, in order to validate with end users whether the proposed solution actually solves the identified problem before investing in aspects such as advanced observability, scalability, or additional integrations. Once the use case is validated, I would then focus on hardening the solution for production: containerization, continuous integration, monitoring, and deployment on robust cloud infrastructure.

In summary: correctly diagnose the nature of the problem (retrieval vs. reasoning), design with decoupled, testable modules, and validate early with real data before scaling the infrastructure.