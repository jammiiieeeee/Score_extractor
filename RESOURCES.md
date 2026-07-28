# Resources for Learning Clean Architecture

## Primary Learning Materials

### 1. Architecture Overview
**File:** `reference/clean-architecture.html`
- Complete beginner's guide to Clean Architecture
- Visual diagrams of the four-layer structure
- Real code examples from this project
- Key benefits and practical applications

### 2. Glossary
**File:** `reference/architecture-glossary.html`
- Definitions of all key terms
- Code examples for each concept
- Quick reference for terminology

### 3. Interactive Quiz
**File:** `reference/architecture-quiz.html`
- Test your understanding
- Immediate feedback on answers
- Explanations for each question

## Project Structure Reference

```
src/
├── api/                    # API Layer (Entry Points)
│   └── gui_api.py          # PyQt6 GUI
├── application/            # Application Layer (Orchestration)
│   ├── use_cases.py        # Business workflows
│   └── extraction_components.py
├── domain/                 # Domain Layer (Core Business Logic)
│   ├── models.py           # Business objects
│   ├── interfaces.py       # Abstract contracts
│   └── deduplication.py    # Business rules
└── infrastructure/         # Infrastructure Layer (Implementations)
    ├── video_service.py    # OpenCV implementation
    ├── ocr_service.py      # PaddleOCR implementation
    └── pdf_service.py      # ReportLab implementation
```

## Key Files to Study

### Start Here (Beginner)
1. `src/domain/models.py` - Pure business objects
2. `src/domain/interfaces.py` - Contracts and abstractions
3. `reference/clean-architecture.html` - Visual learning

### Next Steps (Intermediate)
1. `src/application/use_cases.py` - Workflow orchestration
2. `src/infrastructure/video_service.py` - Concrete implementation
3. `reference/architecture-quiz.html` - Test understanding

### Advanced
1. `src/domain/deduplication.py` - Complex business logic
2. `src/application/extraction_components.py` - Component design
3. `src/api/gui_api.py` - API layer implementation

## External Resources

### Official Clean Architecture
- [Robert C. Martin's Original Article](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- [Clean Architecture Book](https://www.oreilly.com/library/view/clean-architecture/9780134494166/)

### Python-Specific
- [Python Architecture Patterns](https://python-patterns.guide/)
- [Dependency Injection in Python](https://github.com/ets-labs/python-dependency-injector)

### Testing
- [Mocking in Python](https://realpython.com/mocking-python/)
- [pytest Documentation](https://docs.pytest.org/)

## Learning Path

### Week 1: Foundations
- [ ] Read `reference/clean-architecture.html`
- [ ] Study `src/domain/models.py` and `src/domain/interfaces.py`
- [ ] Complete the interactive quiz
- [ ] Review glossary terms

### Week 2: Application
- [ ] Study `src/application/use_cases.py`
- [ ] Understand dependency injection patterns
- [ ] Explore how use cases use interfaces
- [ ] Look at `src/infrastructure/video_service.py`

### Week 3: Practice
- [ ] Try to identify all four layers in the codebase
- [ ] Find examples of the Dependency Rule
- [ ] Understand how testing works with mocks
- [ ] Explore the API layer (`src/api/gui_api.py`)

### Week 4: Mastery
- [ ] Explain Clean Architecture to someone else
- [ ] Identify areas for improvement in the codebase
- [ ] Consider how you'd add a new feature using these patterns
- [ ] Study advanced patterns in `src/domain/deduplication.py`

## Community & Further Learning

### Online Communities
- [r/softwarearchitecture](https://www.reddit.com/r/softwarearchitecture/)
- [Software Engineering Stack Exchange](https://softwareengineering.stackexchange.com/)
- [Clean Coder Blog](https://blog.cleancoder.com/)

### Books
- "Clean Architecture" by Robert C. Martin
- "Domain-Driven Design" by Eric Evans
- "Working Effectively with Legacy Code" by Michael Feathers

## Quick Reference Card

| Concept | Location in Project | Purpose |
|---------|-------------------|---------|
| Business Rules | `src/domain/` | Core logic |
| Interfaces | `src/domain/interfaces.py` | Contracts |
| Use Cases | `src/application/` | Workflows |
| Implementations | `src/infrastructure/` | External services |
| Entry Points | `src/api/` | User interfaces |

---

*Last Updated: 2026-07-22*
*Lesson: Clean Architecture Fundamentals*
