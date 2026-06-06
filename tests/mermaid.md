---
checksum: 76307bbee25a287de4c2ac8db20bb4e06212f01a26f27bc9505a8460dd4336f0
checksum_algorithm: sha256
---
# Mermaid Diagram Examples

This file demonstrates the MERMAID placeholder functionality. Run `mdship update mermaid.md` to render all diagrams.

**Note:** In diagram source code, use `--\>` instead of `-->` to prevent premature closure of the HTML comment marker.

## System Architecture

<!--MERMAID
file: "_diagrams/architecture.svg"
diagram: |
  flowchart LR
    A[Client] --\> B[API Server]
    B --\> C[(Database)]
    B --\> D[Cache]
    D --\> E[Redis]
-->
![diagram](_diagrams/architecture.svg)
<!--/MERMAID-->

The diagram shows the basic system architecture with a client, API server, database, and caching layer.

## User Authentication Flow

<!--MERMAID
file: "_diagrams/auth_flow.svg"
diagram: |
  sequenceDiagram
    participant User
    participant App
    participant API
    participant DB
    User--\>>App: Enter credentials
    App--\>>API: POST /login
    API--\>>DB: Query user
    DB--\>>API: User data
    API--\>>API: Hash password
    API--\>>App: JWT token
    App--\>>User: Redirect to dashboard
-->
![diagram](_diagrams/auth_flow.svg)
<!--/MERMAID-->

This sequence diagram illustrates the authentication flow from user login through token generation.

## Data Processing Pipeline

<!--MERMAID
file: "_diagrams/pipeline.svg"
diagram: |
  flowchart TD
    A[Raw Data] --\> B[Validation]
    B --\> C{Valid?}
    C --\>|No| D[Error Handler]
    D --\> E[Log Error]
    C --\>|Yes| F[Transform]
    F --\> G[Enrich]
    G --\> H[Store]
    H --\> I[Success]
-->
![diagram](_diagrams/pipeline.svg)
<!--/MERMAID-->

This flowchart shows how data flows through the processing pipeline with validation and error handling.

## Database Schema Relationships

<!--MERMAID
file: "_diagrams/schema.svg"
diagram: |
  erDiagram
    USERS ||--o{ POSTS : writes
    USERS ||--o{ COMMENTS : creates
    POSTS ||--o{ COMMENTS : receives
    USERS {
      int id PK
      string email UK
      string password
      string name
      datetime created_at
    }
    POSTS {
      int id PK
      int user_id FK
      string title
      string content
      datetime created_at
    }
    COMMENTS {
      int id PK
      int post_id FK
      int user_id FK
      string content
      datetime created_at
    }
-->
![diagram](_diagrams/schema.svg)
<!--/MERMAID-->

This ER diagram shows the relationships between users, posts, and comments in the database schema.

## Deployment Process

<!--MERMAID
file: "_diagrams/deployment.svg"
diagram: |
  flowchart LR
    A[Source Code] --\> B[Build]
    B --\> C[Test]
    C --\> D{Tests Pass?}
    D --\>|No| E[Notify Developer]
    D --\>|Yes| F[Build Docker Image]
    F --\> G[Push to Registry]
    G --\> H[Deploy to Staging]
    H --\> I[Smoke Tests]
    I --\> J{Ready?}
    J --\>|No| E
    J --\>|Yes| K[Deploy to Production]
-->
![diagram](_diagrams/deployment.svg)
<!--/MERMAID-->

This diagram illustrates the continuous integration and deployment pipeline.

## Software Architecture Class Diagram

<!--MERMAID
file: "_diagrams/classes.svg"
diagram: |
  classDiagram
    class User {
      -int id
      -string email
      -string password
      +login(email, password) bool
      +logout() void
    }
    class Post {
      -int id
      -string title
      -string content
      -int user_id
      +publish() void
    }
    class Comment {
      -int id
      -string text
      -int post_id
      +delete() void
    }
    User "1" --\> "many" Post
    Post "1" --\> "many" Comment
-->
![diagram](_diagrams/classes.svg)
<!--/MERMAID-->

This class diagram shows the relationships between User, Post, and Comment classes.

## Application State Machine

<!--MERMAID
file: "_diagrams/state.svg"
theme: "dark"
diagram: |
  stateDiagram-v2
    [*] --\> Idle
    Idle --\> Loading: Fetch Data
    Loading --\> Ready: Success
    Loading --\> Error: Failed
    Ready --\> Processing: User Action
    Processing --\> Ready: Complete
    Error --\> Idle: Retry
    Ready --\> [*]
-->
![diagram](_diagrams/state.svg)
<!--/MERMAID-->

This state diagram shows the different states of an application and transitions between them.

## Dark Theme Example

<!--MERMAID
file: "_diagrams/dark_example.svg"
theme: "dark"
diagram: |
  flowchart LR
    A[Client Request] --\> B[Authentication]
    B --\>|Valid| C[Process Request]
    B --\>|Invalid| D[Return Error]
    C --\> E[Database Query]
    E --\> F[Format Response]
    F --\> G[Return to Client]
    D --\> G
-->
![diagram](_diagrams/dark_example.svg)
<!--/MERMAID-->

This diagram demonstrates the use of the `theme` parameter with the "dark" theme, which renders with a dark color scheme suitable for dark-mode documentation.

## How to Use

After running `mdship update mermaid.md`:

1. **SVG files are created** in the `_diagrams/` directory
2. **Image markdown** replaces the diagram configuration
3. **Markers are preserved**, so you can update diagrams by running the command again
4. **Idempotent**, so running it multiple times produces the same result

All diagrams support configuration options in the YAML header:

- `file`: Output file path (required, relative to the markdown file)
- `diagram`: Mermaid diagram source code (required)
- `_terminate_`: Custom closing marker name (optional, default: `/MERMAID`)

## Important: Escaping Arrow Syntax

When using arrow syntax (`-->`, `-->>`, etc.) in your Mermaid diagrams, you must escape the closing part:

| Mermaid Syntax | In HTML Comment | Result |
|---|---|---|
| `A --> B` | `A --\> B` | Arrow rendered correctly |
| `A -->> B` | `A --\>> B` | Arrow rendered correctly |
| `A <-- B` | `A <--\> B` (or just `A <-- B`) | Arrow rendered correctly |

The `--\>` is automatically converted to `-->` before rendering, but this prevents the HTML comment from closing prematurely.

## Supported Diagram Types

- **Flowchart**: `flowchart TD`, `flowchart LR`
- **Sequence diagram**: `sequenceDiagram`
- **Entity Relationship**: `erDiagram`
- **Class diagram**: `classDiagram`
- **State diagram**: `stateDiagram-v2`
- **Pie chart**: `pie title`
- And other Mermaid diagram types

## Notes

- Diagrams are rendered using the Mermaid syntax
- SVG output is used by default (PNG requires cairosvg)
- File paths are relative to the markdown file location
- Intermediate directories are created automatically
