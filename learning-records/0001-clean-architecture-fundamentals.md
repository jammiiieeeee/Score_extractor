# Learning Record: Clean Architecture Fundamentals

**Date:** 2026-07-22  
**Lesson:** Clean Architecture Overview  
**Topic:** Software Design Patterns

## What Was Learned

### Core Concepts
- **Four-Layer Architecture:** API → Application → Domain ← Infrastructure
- **Dependency Rule:** Dependencies only point inward; inner layers never depend on outer layers
- **Interface-Based Design:** Contracts (interfaces) in Domain layer, implementations in Infrastructure

### Real-World Examples from Project
- `src/domain/models.py`: Pure business objects (Frame class)
- `src/domain/interfaces.py`: Abstract contracts (IVideoService, IOcrService)
- `src/application/use_cases.py`: Orchestration (ExtractScoreUseCase)
- `src/infrastructure/video_service.py`: Concrete implementation using OpenCV

### Key Benefits Discovered
1. **Testability:** Can mock interfaces to test business logic without external dependencies
2. **Flexibility:** Swapping implementations only requires changing one file
3. **Maintainability:** Clear boundaries make code organization obvious
4. **Scalability:** Pattern works from small projects to enterprise systems

## Insights
- The Domain layer is the heart—contains only business rules
- Interfaces define "what" needs to happen, not "how"
- Use cases orchestrate workflows using injected dependencies
- Infrastructure handles all external integrations (OpenCV, PaddleOCR, etc.)

## Questions for Follow-up
- How would you add a new OCR engine to this system?
- What would happen if we wanted to support video formats besides MP4?
- How does this architecture help with team collaboration?

## Next Steps
- Explore Dependency Injection patterns in more detail
- Learn about testing strategies with mocked interfaces
- Study how to refactor existing code to Clean Architecture

## Reference Materials
- [Clean Architecture - Uncle Bob](https://blog.cleancoder.com/uncle-bob/2012/08/13/the-clean-architecture.html)
- Project structure: `reference/clean-architecture.html`
- Glossary: `reference/architecture-glossary.html`
