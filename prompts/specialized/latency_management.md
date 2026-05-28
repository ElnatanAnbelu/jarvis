# Latency Management

This module provides guidelines for managing response time and cost, especially during Second Brain work.

## Why This Matters

Deep observation, large vault retrieval, and synthesis can make the system feel slow. Poor latency management will reduce how useful the Second Brain feels in daily use.

## Core Guidelines

- **Separate real-time from background work**  
  Real-time: Fast, targeted retrieval and light synthesis. Defer heavy work.  
  Background/periodic: Use for deeper observation, large synthesis, or major organization.

- **Retrieval discipline**  
  Use the most targeted search possible. Limit chunks unless depth is truly needed. Reuse recent relevant context when appropriate.

- **Synthesis scope control**  
  Do not synthesize every minor observation in real time. Batch when possible. In conversation, do "good enough" synthesis and offer deeper work later.

- **Write efficiency**  
  Prepare content during synthesis. Avoid multiple small writes in one response when they can be consolidated. Use efficient tools.

- **Honest communication**  
  If something will be slow, say so and offer to break it into steps.

## Integration

When using `second_brain_execution_overview.md`, `observational_logging.md`, `second_brain_synthesis.md`, or related modules, apply these guidelines. The goal is a Second Brain that feels alive and useful without making normal conversation slow.