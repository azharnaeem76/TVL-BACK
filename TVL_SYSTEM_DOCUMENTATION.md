# TVL - The Virtual Lawyer
## Comprehensive System & Business Documentation

**Business Owner:** Azhar Naeem
**Platform:** AI-Powered Pakistani Legal Assistant
**Version:** 1.0
**Last Updated:** March 2026

---

## Table of Contents
1. [Executive Summary](#1-executive-summary)
2. [Business Overview](#2-business-overview)
3. [System Architecture](#3-system-architecture)
4. [Technology Stack](#4-technology-stack)
5. [Features & Modules](#5-features--modules)
6. [Database Schema](#6-database-schema)
7. [API Reference](#7-api-reference)
8. [AI & Machine Learning](#8-ai--machine-learning)
9. [User Roles & Permissions](#9-user-roles--permissions)
10. [Deployment & Setup](#10-deployment--setup)
11. [Data Pipeline](#11-data-pipeline)
12. [Security](#12-security)
13. [Future Roadmap](#13-future-roadmap)

---

## 1. Executive Summary

TVL (The Virtual Lawyer) is a comprehensive AI-powered legal technology platform designed specifically for Pakistani law. It serves lawyers, judges, law students, and clients by providing:

- **AI Legal Chat** - Ask legal questions in English, Urdu, or Roman Urdu and get answers grounded in Pakistani law with case law citations
- **Scenario Search** - Describe a legal scenario and get relevant case laws, statutes, and AI analysis using semantic vector search
- **Legal Database** - Browse 4,900+ case laws and 439 statutes from all Pakistani courts
- **Document Drafting** - Generate legal documents (FIRs, bail applications, writs, suits) using AI
- **Document Analysis** - Upload legal PDFs for AI-powered summarization and analysis
- **Real-time Messaging** - Secure lawyer-to-lawyer and client-to-lawyer messaging with file sharing
- **Case Tracking** - Track and manage ongoing legal cases
- **Client CRM** - Manage client information and case history
- **Study Materials** - Legal education content for law students
- **Moot Court** - Practice moot court sessions with AI evaluation
- **Legal Forum** - Community discussion board for legal topics

The platform is built with a **Next.js** frontend and **FastAPI** backend, using **PostgreSQL** for data storage, **Ollama** (local LLM) for AI, and **sentence-transformers** for semantic search embeddings.

---

## 2. Business Overview

### 2.1 Problem Statement
Pakistani legal professionals face several challenges:
- Access to case law databases is expensive and fragmented
- Finding relevant precedents requires extensive manual research
- Legal advice in Urdu/Roman Urdu is not readily available digitally
- Document drafting is time-consuming and error-prone
- Communication between lawyers and clients lacks secure digital channels

### 2.2 Solution
TVL addresses these challenges by providing a unified platform that:
- Offers a free, searchable database of Pakistani case laws and statutes
- Uses AI to find semantically relevant case laws for any legal scenario
- Supports multilingual interaction (English, Urdu, Roman Urdu)
- Automates legal document drafting with customizable templates
- Provides secure real-time messaging between legal professionals and clients

### 2.3 Target Users
| Role | Use Cases |
|------|-----------|
| **Lawyers** | Case research, document drafting, client management, messaging |
| **Judges** | Case law reference, legal research, analysis |
| **Law Students** | Study materials, moot court practice, legal learning |
| **Clients** | Legal advice, lawyer communication, case tracking |
| **Admin** | User management, feature toggles, content management |

### 2.4 Revenue Model (Proposed)
- **Freemium**: Basic search and limited AI queries free
- **Professional**: Unlimited AI chat, document drafting, client CRM
- **Enterprise**: Multi-user law firm access, API access, custom branding
- **Subscription tiers** managed via the built-in subscription system

---

## 3. System Architecture

```
                    ┌─────────────────┐
                    │   Next.js 14    │
                    │   Frontend      │
                    │   Port 3000     │
                    └────────┬────────┘
                             │ HTTP / WebSocket
                    ┌────────▼────────┐
                    │   FastAPI       │
                    │   Backend       │
                    │   Port 8000     │
                    └──┬──────┬───┬───┘
                       │      │   │
              ┌────────▼──┐ ┌─▼───▼────────┐
              │ PostgreSQL │ │   Ollama      │
              │ Database   │ │   (Local LLM) │
              │ tvl_db     │ │   Port 11434  │
              └────────────┘ └──────────────┘
                                    │
                             ┌──────▼──────┐
                             │  qwen2.5:7b │
                             │  AI Model   │
                             └─────────────┘
```

### 3.1 Frontend (Next.js 14)
- **Location:** `tvl-ai/frontend/`
- **Framework:** Next.js 14 with App Router
- **Styling:** Tailwind CSS with custom court-themed design system
- **State:** React hooks + localStorage for auth tokens
- **Real-time:** Socket.IO client for messaging notifications

### 3.2 Backend (FastAPI)
- **Location:** `tvl-ai/backend/`
- **Framework:** FastAPI with async support
- **ORM:** SQLAlchemy 2.0 (async)
- **Auth:** JWT tokens with bcrypt password hashing
- **Real-time:** Socket.IO (python-socketio) for messaging
- **AI Integration:** Ollama API for LLM, sentence-transformers for embeddings

### 3.3 Database (PostgreSQL)
- **Database:** tvl_db
- **Tables:** 20+ tables covering users, legal data, messaging, forums, etc.
- **Seeding:** Auto-seeds on startup with 4,900+ case laws, 439 statutes, sections, and study content

---

## 4. Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js 14 | React framework with SSR |
| Styling | Tailwind CSS | Utility-first CSS |
| Backend | FastAPI | Async Python web framework |
| Database | PostgreSQL | Relational database |
| ORM | SQLAlchemy 2.0 | Async database ORM |
| Auth | JWT + bcrypt | Authentication & authorization |
| AI/LLM | Ollama (qwen2.5:7b) | Local AI model for chat & analysis |
| Embeddings | sentence-transformers | Semantic search vectors (384-dim) |
| Embedding Model | paraphrase-multilingual-MiniLM-L12-v2 | Multilingual embedding model |
| Real-time | Socket.IO | WebSocket messaging |
| File Upload | FastAPI UploadFile | Document and media handling |
| PDF Parsing | pdfplumber | Extract text from legal PDFs |
| HTTP Client | httpx | Async HTTP for Ollama API |

---

## 5. Features & Modules

### 5.1 AI Legal Chat (`/chat`)
- Conversational AI assistant specialized in Pakistani law
- Supports English, Urdu, and Roman Urdu
- Streaming responses (Server-Sent Events) for real-time typing effect
- Chat session management (create, load, delete sessions)
- Context-aware: uses database references as primary source
- Cited case laws displayed in sidebar panel
- Fallback mode when Ollama is unavailable

### 5.2 Scenario Search (`/search`)
- Describe any legal scenario in natural language
- AI detects language and normalizes query
- Vector similarity search across 4,900+ case laws using embeddings
- Text-based fallback search when embeddings unavailable
- Filters by category, court, year range
- AI-generated analysis with citations
- Search history and saved searches
- Case comparison view
- Citation graph visualization

### 5.3 Case Laws Library (`/case-laws`)
- Browse 4,900+ Pakistani case laws
- Filter by category (14 categories), court (12 courts), year
- Full-text search on title, citation, sections, headnotes
- Expandable case cards with full details
- Reading mode for focused study
- PDF export of case details
- Bookmark system with notes
- Statute reference badges (PPC, CrPC, etc.)

### 5.4 Statutes & Sections (`/statutes`)
- Browse 439 Pakistani statutes
- Drill into sections for each statute
- Category filtering
- Search within sections
- Full text and summaries in English and Urdu

### 5.5 Document Drafting (`/drafting`)
- 20+ legal document templates including:
  - FIR Application
  - Bail Applications (pre-arrest, post-arrest, cancellation)
  - Writ Petitions (Article 199)
  - Suit for Recovery / Possession / Pre-emption
  - Maintenance Suit, Guardianship Petition, Dower Recovery
  - Temporary Injunction, Written Statement
  - Labor Court Complaint
  - Rent Petition, Power of Attorney, Legal Notice
  - General Affidavit, Sale Agreement
- AI-powered generation using Ollama
- Customizable fields per template
- Download generated documents

### 5.6 Document Analysis (`/documents`)
- Upload PDF or TXT legal documents
- AI-powered analysis extracting:
  - Document summary
  - Parties involved
  - Relevant sections
  - Court references
  - Key findings
- Analysis status tracking (pending → analyzing → completed)

### 5.7 Messaging (`/messaging`)
- Real-time 1:1 messaging between users
- Message types: text, image, file, voice, video
- File upload (max 25MB) with type validation
- Voice recording with duration tracking
- Read receipts and unread counts
- Conversation deletion
- Socket.IO for instant message delivery
- Typing indicators

### 5.8 Case Tracker (`/case-tracker`)
- Create and manage ongoing legal cases
- Track case status, dates, and details
- Link to relevant case laws and documents
- Status updates and timeline

### 5.9 Client CRM (`/clients`)
- Manage client database
- Client details (name, contact, address)
- Link clients to cases
- Add/edit/delete clients

### 5.10 Study Materials (`/study`)
- 145+ legal education content pieces
- Categories: Criminal, Civil, Constitutional, Family, Property, etc.
- Content types: articles, case analyses, exam prep
- Difficulty levels: beginner, intermediate, advanced
- Urdu summaries available

### 5.11 Moot Court (`/moot-court`)
- Practice moot court sessions
- AI-evaluated arguments
- Scoring and feedback

### 5.12 Legal Forum (`/forum`)
- Community discussion board
- Categories and topic threads
- Upvoting and replies

### 5.13 Admin Panel (`/admin`)
- User management (create, edit, suspend, activate)
- Role assignment (admin, lawyer, judge, student, client)
- Feature toggles (enable/disable modules)
- Case law management (add/edit)
- Content management

### 5.14 Additional Features
- **Voice Search** - Speech-to-text input for search and chat
- **Bookmarks** - Save and organize case laws with personal notes
- **Annotations** - Add personal annotations to case laws
- **PDF Export** - Export case law details as PDF
- **Share Links** - Copy case law citations and links
- **Dark Theme** - Court-themed dark UI with brass accents
- **Responsive Design** - Mobile-first responsive layout
- **Multilingual Support** - English, Urdu, Roman Urdu

---

## 6. Database Schema

### 6.1 Core Tables

#### Users
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | User ID |
| email | String | Unique email |
| hashed_password | String | bcrypt hash |
| full_name | String | Display name |
| role | Enum | admin/lawyer/judge/student/client |
| is_active | Boolean | Account active |
| is_suspended | Boolean | Account suspended |
| phone, city, bar_council_id | String | Profile fields |

#### Case Laws
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Case law ID |
| citation | String (unique) | Legal citation (e.g., "2025 SCMR 856") |
| title | String | Case title |
| court | Enum | Court name (12 courts) |
| category | Enum | Law category (14 categories) |
| year | Integer | Year of judgment |
| judge_name | String | Presiding judge |
| summary_en | Text | English summary |
| summary_ur | Text | Urdu summary |
| headnotes | Text | Legal headnotes |
| relevant_statutes | Text | Referenced statutes |
| sections_applied | Text (JSON) | Sections applied (e.g., ["Section 302 PPC"]) |
| embedding | Text (JSON) | 384-dim vector embedding |
| created_at | DateTime | Record creation date |

#### Statutes
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Statute ID |
| title | String | Statute name |
| act_number | String | Act/Ordinance number |
| year | Integer | Year of enactment |
| category | Enum | Law category |
| full_text | Text | Full statute text |
| summary_en | Text | English summary |
| summary_ur | Text | Urdu summary |
| embedding | Text (JSON) | 384-dim vector embedding |

#### Sections
| Column | Type | Description |
|--------|------|-------------|
| id | Integer (PK) | Section ID |
| statute_id | Integer (FK) | Parent statute |
| section_number | String | Section number |
| title | String | Section title |
| content | Text | Section content (English) |
| content_ur | Text | Section content (Urdu) |

### 6.2 Law Categories (Enum)
Criminal, Civil, Constitutional, Family, Corporate, Taxation, Labor, Property, Cyber, Banking, Intellectual Property, Human Rights, Environmental, Islamic

### 6.3 Courts (Enum)
Supreme Court, Federal Shariat Court, Lahore/Sindh/Peshawar/Balochistan/Islamabad High Courts, District Court, Session Court, Family Court, Banking Court, Anti-Terrorism Court

### 6.4 Data Volume
| Table | Records |
|-------|---------|
| Case Laws | 4,909 |
| Statutes | 439 |
| Sections | 500+ |
| Study Content | 145 |
| Embeddings | 5,348 (all case laws + statutes) |

---

## 7. API Reference

Base URL: `http://localhost:8000/api/v1`

### 7.1 Authentication
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/register` | POST | Register new user |
| `/auth/login` | POST | Login, returns JWT token |
| `/auth/me` | GET | Get current user profile |
| `/auth/forgot-password` | POST | Request password reset |
| `/auth/reset-password` | POST | Reset password with token |

### 7.2 Search
| Endpoint | Method | Auth | Description |
|----------|--------|------|-------------|
| `/search/scenario` | POST | Yes | AI-powered scenario search |

### 7.3 Legal Database
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/legal/case-laws` | GET | List case laws with filters |
| `/legal/case-laws/{id}` | GET | Get case law detail |
| `/legal/statutes` | GET | List statutes |
| `/legal/statutes/{id}` | GET | Get statute detail |
| `/legal/statutes/{id}/sections` | GET | Get statute sections |

### 7.4 AI Chat
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat/message` | POST | Send message, get AI response |
| `/chat/message/stream` | POST | Streaming AI response (SSE) |
| `/chat/sessions` | GET | List chat sessions |
| `/chat/sessions/{id}/messages` | GET | Get session messages |
| `/chat/sessions/{id}` | DELETE | Delete chat session |

### 7.5 Messaging
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/messaging/conversations` | GET | List conversations |
| `/messaging/send` | POST | Send text message |
| `/messaging/send-file` | POST | Send file/media |
| `/messaging/conversations/{id}/messages` | GET | Get messages |
| `/messaging/conversations/{id}/read` | POST | Mark as read |
| `/messaging/files/{filename}` | GET | Serve uploaded file |

### 7.6 Document Drafting & Analysis
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/ai-tools/draft` | POST | Generate legal document |
| `/ai-tools/documents/upload` | POST | Upload document |
| `/ai-tools/documents/{id}/analyze` | POST | Analyze document |

### 7.7 Admin
| Endpoint | Method | Description |
|----------|--------|-------------|
| `/admin/users` | GET | List all users |
| `/admin/users` | POST | Create user |
| `/admin/users/{id}` | PUT | Update user |
| `/admin/features` | GET/PUT | Manage feature toggles |

Full API documentation available at: `http://localhost:8000/docs` (Swagger UI)

---

## 8. AI & Machine Learning

### 8.1 Language Detection
- Automatically detects English, Urdu, or Roman Urdu input
- Normalizes queries to English for embedding generation
- Responds in the user's preferred language

### 8.2 Embedding Model
- **Model:** `paraphrase-multilingual-MiniLM-L12-v2`
- **Dimensions:** 384
- **Languages:** 50+ including English and Urdu
- **Storage:** JSON-encoded vectors in PostgreSQL Text columns
- **Total embeddings:** 5,348 (4,909 case laws + 439 statutes)

### 8.3 Semantic Search Pipeline
1. User inputs legal scenario (any language)
2. Language detection → normalize to English
3. Generate 384-dim query embedding
4. Cosine similarity search against all case law embeddings
5. Filter by category/court/year if specified
6. Return top matches above similarity threshold (default: 0.5)
7. Generate AI analysis citing the found cases

### 8.4 LLM Configuration
- **Provider:** Ollama (local, free)
- **Model:** qwen2.5:7b (7 billion parameters)
- **Temperature:** 0.3 (focused, accurate responses)
- **Max tokens:** 2,048
- **Timeout:** 180 seconds
- **System prompt:** Pakistani law specialist with strict citation rules

### 8.5 Fallback Strategy
When Ollama is unavailable:
- Text-based ILIKE search replaces vector search
- Structured database results returned without AI analysis
- User notified that AI analysis is temporarily unavailable

---

## 9. User Roles & Permissions

| Feature | Client | Student | Lawyer | Judge | Admin |
|---------|--------|---------|--------|-------|-------|
| AI Chat | Yes | Yes | Yes | Yes | Yes |
| Scenario Search | Yes | Yes | Yes | Yes | Yes |
| Case Laws | Yes | Yes | Yes | Yes | Yes |
| Statutes | Yes | Yes | Yes | Yes | Yes |
| Document Drafting | No | No | Yes | Yes | Yes |
| Document Analysis | No | No | Yes | Yes | Yes |
| Messaging | Yes | Yes | Yes | Yes | Yes |
| Case Tracker | No | No | Yes | Yes | Yes |
| Client CRM | No | No | Yes | No | Yes |
| Study Materials | Yes | Yes | Yes | Yes | Yes |
| Moot Court | No | Yes | Yes | Yes | Yes |
| Forum | Yes | Yes | Yes | Yes | Yes |
| Admin Panel | No | No | No | No | Yes |

---

## 10. Deployment & Setup

### 10.1 Prerequisites
- Python 3.11+
- Node.js 18+
- PostgreSQL 14+
- Ollama (for AI features)

### 10.2 Quick Start

```bash
# 1. Setup AI Model (one-time)
# Download and install Ollama from https://ollama.ai
ollama pull qwen2.5:7b

# 2. Create database
psql -U postgres -c "CREATE DATABASE tvl_db"

# 3. Backend setup
cd tvl-ai/backend
pip install -r requirements.txt
uvicorn app.main:app --reload

# 4. Frontend setup
cd tvl-ai/frontend
npm install
npm run dev

# 5. Access the application
# Open http://localhost:3000
```

### 10.3 Demo Accounts
| Email | Password | Role |
|-------|----------|------|
| admin@tvl.pk | demo123 | Admin |
| lawyer@tvl.pk | demo123 | Lawyer |
| judge@tvl.pk | demo123 | Judge |
| student@tvl.pk | demo123 | Student |
| client@tvl.pk | demo123 | Client |

### 10.4 Environment Configuration
Key settings in `backend/app/core/config.py`:
- `DATABASE_URL` - PostgreSQL connection string
- `SECRET_KEY` - JWT signing key
- `OLLAMA_BASE_URL` - Ollama server URL (default: http://localhost:11434)
- `OLLAMA_MODEL` - AI model name (default: qwen2.5:7b)
- `EMBEDDING_MODEL` - Embedding model (default: paraphrase-multilingual-MiniLM-L12-v2)
- `HF_HOME` - Hugging Face model cache directory
- `SIMILARITY_THRESHOLD` - Minimum cosine similarity for search results (default: 0.5)

### 10.5 Generating Embeddings
After initial setup, generate embeddings for semantic search:
```bash
cd tvl-ai/backend
python generate_embeddings.py
```
This processes all case laws and statutes (~5,000 records) in batches.

---

## 11. Data Pipeline

### 11.1 Data Sources
1. **Case Laws (4,909)** - Pakistani court judgments from Supreme Court, High Courts, and subordinate courts
2. **Statutes (439)** - Pakistani legislation parsed from PDF files in `PakistanLaw/laws_of_pakistan/` directory (389 PDFs across 30 categories)
3. **Sections (500+)** - Individual sections from major statutes (PPC, CrPC, CPC, Constitution, MFLO, PECA, etc.)
4. **Study Content (145)** - Educational materials for law students

### 11.2 Data Seeding
The system auto-seeds on startup via the FastAPI lifespan handler:
1. `seed_data.py` - Base case laws, statutes, and demo users
2. `seed_case_laws.py` - 4,900+ comprehensive case laws
3. `seed_statutes.py` - Core statutes with summaries
4. `seed_sections.py` - Statute sections from `real_sections.json`
5. `seed_pakistan_laws.py` - Additional statutes from parsed PDFs
6. `seed_study_content_data.py` - Study materials

### 11.3 Pakistan Law PDF Parser
`tvlDump/parse_pakistan_laws.py` processes PDFs from the PakistanLaw directory:
- Extracts title and year from filenames
- Reads first 3 pages for summary text
- Maps to law categories
- Outputs `pakistan_law_statutes.json` for database seeding

---

## 12. Security

### 12.1 Authentication
- JWT tokens with configurable expiration
- bcrypt password hashing (salt rounds auto-managed)
- Token stored in localStorage as `tvl_token`
- Protected routes require valid JWT in Authorization header

### 12.2 Authorization
- Role-based access control (admin, lawyer, judge, student, client)
- Account suspension/deactivation checks on every authenticated request
- Admin-only endpoints for user and content management

### 12.3 Input Validation
- Pydantic schemas validate all API inputs
- File upload type and size validation (max 25MB)
- Directory traversal prevention on file serving
- SQL injection prevention via SQLAlchemy parameterized queries

### 12.4 Real-time Security
- Socket.IO connections authenticated via JWT token
- User-to-SID mapping for targeted message delivery
- Sender exclusion to prevent message echo

---

## 13. Future Roadmap

### Phase 2 (Proposed)
- [ ] Full-text search with PostgreSQL tsvector (replace ILIKE)
- [ ] pgvector extension for native vector similarity search
- [ ] PDF full-text indexing for case law documents
- [ ] Payment integration for subscription tiers
- [ ] Mobile app (React Native)
- [ ] Multi-language UI (complete Urdu interface)
- [ ] Advanced analytics dashboard for admin
- [ ] API rate limiting and usage tracking
- [ ] Cloud deployment (AWS/GCP/Azure)
- [ ] Automated case law ingestion pipeline
- [ ] Integration with court filing systems

### Phase 3 (Proposed)
- [ ] Fine-tuned LLM on Pakistani legal corpus
- [ ] Automated legal document review
- [ ] Court date reminders and calendar integration
- [ ] Video consultation scheduling
- [ ] Legal marketplace (find a lawyer)
- [ ] Multi-tenant SaaS for law firms

---

## Contact

**Business Owner:** Azhar Naeem
**Platform:** TVL - The Virtual Lawyer
**Tagline:** *"According to Spirit of Law"*

---

*This document was generated as part of the TVL system development. For technical support or inquiries, please contact the development team.*
