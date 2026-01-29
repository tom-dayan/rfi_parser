# RFI & Submittal Processing Tool

## What Is This Tool?

This tool was built for OLI Architecture to automate one of the most time-consuming parts of construction administration: searching through hundreds of pages of project specifications to draft responses to contractor documents. Instead of manually hunting for the right spec sections, the tool does that search automatically and drafts a professional response, saving the team significant time on every project.

## How Does It Work?

The tool works in three steps:

1. **Scan** — You point the tool at your project folders (one for RFIs/Submittals, one for Specifications). It reads and extracts text from all the documents — PDFs, Word files, drawings, and images.

2. **Index** — The tool breaks all specification documents into smaller sections and stores them in a searchable knowledge base. Think of it like building a custom search engine specifically for that project's specs. This means the tool doesn't need to re-read every spec document each time — it already knows what's in them.

3. **Analyze** — When you process a document, the tool searches the knowledge base to find the most relevant specification sections, then sends those sections along with the document content to an AI model that drafts a response with the appropriate spec references.

Every response includes references back to the specific specification sections that were used, so the architect can verify the AI's work before sending anything out.

## What Technology Powers It?

The tool is a web application that runs on your own computer — no data leaves your machine unless you choose to use a cloud AI service.

The **backend** (the engine that does the heavy lifting) is written in Python. It handles reading documents, managing the knowledge base, and communicating with the AI. The **frontend** (what you see and click on) is a modern web interface built with React that runs in your browser.

For AI, the tool uses **Ollama**, which runs large language models directly on your computer. This means your project documents stay private and never get uploaded to the internet. If needed, the tool can also be configured to use Anthropic's Claude API or Google's Gemini for higher-quality responses on complex documents.

The "smart search" behind finding the right spec sections uses a technique called **vector embeddings** — essentially, the tool converts text into mathematical representations that capture meaning, so it can find relevant specs even when the exact words don't match. This is stored in a local database called ChromaDB.

## How Was It Built?

This tool was developed collaboratively between a human architect and an AI assistant (Claude). The architect defined the requirements — the workflows, the expected outputs, and how the tool should fit into the firm's existing processes — and the AI handled the software engineering: writing code, setting up the database, building the user interface, and wiring everything together. The result is a tool tailored to how architecture firms actually work, built in a fraction of the time traditional software development would take.
