# 🎣 Fishing Assistant

An AI-powered fishing assistant focused on recreational fishing in Germany.

The assistant combines **legal retrieval, weather forecasts, personal catch data, and web search** to answer fishing-related questions.

Currently supported German federal states for fishing regulations:

- Baden-Württemberg
- Bavaria
- Berlin
- Brandenburg
- Rhineland-Palatinate

## Features

### ⚖️ Fishing Regulation Retrieval

The assistant can answer questions about fishing regulations based on official fishing regulation documents (*Fischereiverordnungen*) of the supported federal states.

The regulations are stored as PDF documents and processed into chunks. For every chunk, an embedding is generated and stored in a **LanceDB** database together with the original text and metadata such as:

- Federal state (*Bundesland*)
- Page
- Source document

Retrieval uses **hybrid search**, combining:

- **Vector search** for semantic similarity
- **Full-text search** for keyword-based matching
- **Metadata filtering** to restrict results to the relevant federal state

The hybrid search uses LanceDB's internal implementation with its standard weighting and ranking methods.

Currently, retrieval is performed **before every agent call**. This ensures that potentially relevant legal information is always available to the agent. In the future, the retrieval could be moved into a dedicated agent tool so that it is only executed when legal information is required.

**Example prompt:**

> I just caught a salmon in Brandenburg. It's around 40 cm long. Am I allowed to keep it?

---

### 🌦️ Fishing Weather Recommendations

The assistant can recommend suitable fishing days based on the weather forecast for a chosen location.

For weather data, the agent connects to the public Open-Meteo MCP server:

`https://open-meteo.caseyjhand.com/mcp`

The MCP server provides two tools:

- `openmeteo_search_locations`
- `openmeteo_get_forecast`

The location is first resolved and then used to retrieve weather forecasts for up to seven days. Based on these conditions, the agent can recommend a suitable day or period for fishing.

**Example prompt:**

> I want to go fishing in Munich from October 4th to October 7th. Which day would you recommend?

---

### 🐟 Personal Catch Collection

Users can save their catches in a personal catch collection.

A catch can contain information such as:

- Fish species
- Length
- Weight
- Location
- Date

Each catch is stored as an individual record that can later be filtered and analyzed.

The agent has access to tools for retrieving information from the collection. This allows it to answer questions about individual catches as well as aggregated information such as averages, counts, and personal records.

**Example prompt:**

> What is my biggest catch so far, and what is the average catch size in my collection?

---

### 🌐 Web Search

For general fishing knowledge that is not available through the legal documents or personal catch collection, the assistant can use web search.

This can provide additional information about topics such as:

- Typical fish size and weight
- Habitat
- Seasonal behavior
- Feeding behavior and prey
- Fishing techniques
- Water depth and temperature

**Example prompt:**

> Where should I look for pike in autumn, and what are they usually feeding on?

---

### 🔍 Tool Call Visualization

After every agent response, the application displays the tools that were used.

Each tool call can be expanded in the UI to inspect its result. This makes the agent's behavior more transparent and is also useful for debugging.

---

## Future Improvements

- Add fish identification and analysis from uploaded images
- Add more retrieval parameters to the developer panel, such as hybrid-search weights
- Add RAG evaluation using **RAGAS**
- Move fishing regulation retrieval into a dedicated agent tool

---

## Project Requirements

| Requirement | Difficulty | Implementation |
|---|---|---|
| Tool call result visualization | Medium | Tool calls and their results can be expanded in the UI |
| Public remote MCP server | Medium | Open-Meteo MCP server provides location and weather forecast tools |
| Hybrid search | Hard | LanceDB combines vector search, full-text search, and metadata filtering |

---

## Summary

The Fishing Assistant combines **RAG and agentic tool calling** to provide a specialized assistant for recreational anglers.

Its main capabilities are:

**Fishing regulations** → Hybrid retrieval from official fishing regulation documents  
**Fishing conditions** → Weather forecasts through a remote MCP server  
**Personal statistics** → Personal catch collection and analysis  
**General fishing knowledge** → Web search

The result is an assistant that combines legal knowledge, live external information, and personal catch data in a single conversational interface.
