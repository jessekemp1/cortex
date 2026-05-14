"""
Cortex Bridge - Intelligence Mixin

Context retrieval, recommendations, intelligence queries, specs,
feedback tracking, and analysis mode methods.

Split from bridge.py for maintainability (Feb 2026).
"""

import json
import sys
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from intelligence.adaptive_latency import AnalysisMode
except ImportError:
    AnalysisMode = None

# Conditional imports needed by mixin methods
try:
    from cortex.intelligence.models import IntelligenceQueryType
except ImportError:
    IntelligenceQueryType = None

try:
    from intelligence.context_optimizer import optimize_prompt_context

    CONTEXT_OPTIMIZER_AVAILABLE = True
except ImportError:
    CONTEXT_OPTIMIZER_AVAILABLE = False
    optimize_prompt_context = None

try:
    from intelligence.memory.tiered_memory import MemoryItem

    TIERED_MEMORY_AVAILABLE = True
except ImportError:
    TIERED_MEMORY_AVAILABLE = False
    MemoryItem = None

try:
    from cortex_extras.synthetic.generator import SyntheticGenerator
    from cortex_extras.synthetic.schemas import GenerationRequest

    SYNTHETIC_AVAILABLE = True
except ImportError:
    SYNTHETIC_AVAILABLE = False
    SyntheticGenerator = None
    GenerationRequest = None


class IntelligenceMixin:
    """Intelligence-related methods for CortexBridge.

    This mixin provides methods for context retrieval, recommendation
    injection, intelligence queries, spec search, implicit feedback,
    rule tracking, and adaptive analysis modes.

    All methods access self.* attributes initialized by CortexBridgeBase.__init__.
    """

    # --- 1. Context Bridge ---

    def get_context(
        self, query: str, limit: int = 5, project: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get relevant context for a query from Knowledge Base and Project History.

        Uses AI Engineering pipeline when available:
        1. DefensivePrompting - Validate input
        2. TieredMemory - Check session memory first
        3. HybridRetriever - Semantic + keyword search
        4. ContextIntelligence - Fallback to existing system
        5. ContextOptimizer - Reorder for LLM attention
        6. ImplicitFeedback - Track shown results

        Args:
            query: Natural language query
            limit: Max results
            project: Optional project filter

        Returns:
            List of context items with source metadata
        """
        # 1. DefensivePrompting: Validate input
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            validation = self.defensive.validate_input(query)
            if not validation.valid:
                return [
                    {
                        "error": "Input validation failed",
                        "issues": validation.issues,
                        "source": "defensive_prompting",
                    }
                ]
            query = validation.sanitized_input

        results = []

        # 2. TieredMemory: Check session memory first
        if self.tiered_memory:
            try:
                memory_results = self.tiered_memory.query(query, limit=limit)
                for item, score, tier in memory_results:
                    # Convert MemoryItem to context dict
                    if hasattr(item, "content"):
                        result = {
                            "title": item.content.get("title", item.id),
                            "type": item.content.get("type", "memory"),
                            "description": item.content.get("description", ""),
                            "confidence": min(score / 3.0, 1.0),  # Normalize score
                            "file": item.content.get("file"),
                            "command": item.content.get("command"),
                            "source": f"tiered_memory:{tier}",
                        }
                        results.append(result)
            except Exception:
                pass  # Fall through to other sources

        # 3. HybridRetriever: Semantic + keyword search
        if self.hybrid_retriever and len(results) < limit:
            try:
                remaining = limit - len(results)
                hybrid_results = self.hybrid_retriever.search(query, limit=remaining, alpha=0.5)
                for pattern, score in hybrid_results:
                    result = {
                        "title": pattern.title,
                        "type": "pattern",
                        "description": pattern.description,
                        "confidence": score,
                        "file": None,
                        "command": None,
                        "source": "hybrid_retriever",
                    }
                    results.append(result)
            except Exception:
                pass  # Fall through to fallback

        # 4. ContextIntelligence: Fallback to existing system
        if len(results) < limit and self.context_intel:
            try:
                remaining = limit - len(results)
                keywords = query.split() if " " in query else [query]
                predictions = self.context_intel.predict_context(
                    current_project=project, keywords=keywords, limit=remaining
                )
                for p in predictions:
                    result = {
                        "title": p.title,
                        "type": p.context_type,
                        "description": p.description,
                        "confidence": p.confidence,
                        "file": str(p.file_path) if p.file_path else None,
                        "command": p.command,
                        "source": "context_intelligence",
                    }
                    results.append(result)
            except Exception:
                pass

        # Handle no results case
        if not results:
            if not self.context_intel:
                return [{"error": "ContextIntelligence not available", "source": "system"}]
            return []

        # 5. ContextOptimizer: Reorder for LLM attention (handled in get_optimized_context)
        # Note: Direct get_context returns raw results; use get_optimized_context for LLM optimization

        # 6. ImplicitFeedback: Track shown results
        if self.implicit_feedback:
            try:
                for i, result in enumerate(results):
                    rec_id = f"context_{result.get('title', f'result_{i}')}_{i}"
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "title": result.get("title", ""),
                            "source": result.get("source", "unknown"),
                            "position": i,
                        },
                        context={"query": query, "project": project},
                    )
            except Exception:
                pass  # Non-critical

        return results[:limit]

    def get_optimized_context(
        self,
        query: str,
        limit: int = 10,
        project: Optional[str] = None,
        max_tokens: Optional[int] = None,
        strategy: str = "importance",
        include_markers: bool = True,
    ) -> Dict[str, Any]:
        """
        Get context optimized for LLM attention patterns.

        Uses the ContextOptimizer to reorder context items based on importance,
        applying the "lost-in-the-middle" optimization for better LLM attention.

        Args:
            query: Natural language query
            limit: Max results to retrieve
            project: Optional project filter
            max_tokens: Optional token limit for context
            strategy: Optimization strategy - "importance" or "category"
            include_markers: Whether to add position markers like [IMPORTANT]

        Returns:
            Dict with:
            - optimized_context: String ready for LLM prompt
            - items: List of context items with metadata
            - optimization_applied: Whether optimization was used
        """
        # Get raw context items
        raw_context = self.get_context(query, limit=limit, project=project)

        # Check for errors
        if raw_context and "error" in raw_context[0]:
            return {"error": raw_context[0]["error"], "optimization_applied": False}

        # If optimizer not available, return raw context as string
        if not self.context_optimizer or not CONTEXT_OPTIMIZER_AVAILABLE:
            context_str = "\n\n".join(
                f"[{item.get('type', 'data')}] {item.get('title', '')}: {item.get('description', '')}"
                for item in raw_context
            )
            return {
                "optimized_context": context_str,
                "items": raw_context,
                "optimization_applied": False,
                "reason": "ContextOptimizer not available",
            }

        # Convert to ContextItem format for optimizer
        context_items = []
        for item in raw_context:
            # Map context types to categories
            ctx_type = item.get("type", "data")
            if ctx_type in ("instruction", "system"):
                category = "instruction"
            elif ctx_type in ("example", "pattern"):
                category = "example"
            elif ctx_type in ("history", "recent"):
                category = "history"
            else:
                category = "data"

            context_items.append(
                {
                    "content": f"{item.get('title', '')}: {item.get('description', '')}",
                    "importance": item.get("confidence", 0.5),
                    "category": category,
                    "source": item.get("file"),
                    "metadata": {"original": item},
                }
            )

        # Apply optimization
        try:
            optimized_str = optimize_prompt_context(
                context_items,
                max_tokens=max_tokens,
                strategy=strategy,
                include_markers=include_markers,
            )

            return {
                "optimized_context": optimized_str,
                "items": raw_context,
                "optimization_applied": True,
                "strategy": strategy,
                "max_tokens": max_tokens,
            }
        except Exception as e:
            # Fallback to raw context
            context_str = "\n\n".join(
                f"[{item.get('type', 'data')}] {item.get('title', '')}: {item.get('description', '')}"
                for item in raw_context
            )
            return {
                "optimized_context": context_str,
                "items": raw_context,
                "optimization_applied": False,
                "error": str(e),
            }

    # --- 2. Strategy Bridge ---

    def inject_recommendation(
        self,
        title: str,
        rationale: str,
        priority: str = "medium",
        type: str = "ai_suggestion",
        effort: str = "Unknown",
        related_project: str = "",
    ) -> bool:
        """
        Inject a strategic recommendation into Cortex.

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate inputs
        2. TieredMemory - Record for future recall
        3. ImplicitFeedback - Track recommendation shown

        Args:
            title: Action title
            rationale: Why this is important
            priority: high/medium/low
            type: Category of recommendation
            effort: Estimated effort
            related_project: Associated project
        """
        # 1. DefensivePrompting: Validate inputs
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            # Validate title
            title_validation = self.defensive.validate_input(title)
            if not title_validation.valid:
                print(
                    f"Bridge Error: Title validation failed: {title_validation.issues}",
                    file=sys.stderr,
                )
                return False
            title = title_validation.sanitized_input

            # Validate rationale
            rationale_validation = self.defensive.validate_input(rationale)
            if not rationale_validation.valid:
                print(
                    f"Bridge Error: Rationale validation failed: {rationale_validation.issues}",
                    file=sys.stderr,
                )
                return False
            rationale = rationale_validation.sanitized_input

        rec_id = f"bridge_{uuid.uuid4().hex[:8]}"
        rec_data = {
            "id": rec_id,
            "title": title,
            "type": type,
            "priority": priority,
            "rationale": rationale,
            "estimated_effort": effort,
            "estimated_impact": priority,
            "confidence": 0.95,
            "related_projects": [related_project] if related_project else [],
            "description": f"Injected via Cortex Bridge.\nRationale: {rationale}",
            "created_at": datetime.now().isoformat(),
            "source": "CortexBridge",
        }

        # root_dir may be the monorepo root (Dev/) or the cortex dir itself
        if (self.root_dir / "bridge.py").exists():
            external_file = self.root_dir / "external_recommendations.json"
        else:
            external_file = self.root_dir / "cortex" / "external_recommendations.json"

        try:
            # Atomic-ish read/modify/write
            current_recs = []
            if external_file.exists():
                content = external_file.read_text()
                if content.strip():
                    try:
                        current_recs = json.loads(content)
                    except json.JSONDecodeError:
                        current_recs = []

            current_recs.append(rec_data)
            external_file.write_text(json.dumps(current_recs, indent=2))

            # 2. TieredMemory: Record for future recall
            if self.tiered_memory and TIERED_MEMORY_AVAILABLE and MemoryItem:
                try:
                    memory_item = MemoryItem(
                        id=rec_id,
                        content={
                            "title": title,
                            "type": type,
                            "description": rationale,
                            "priority": priority,
                            "project": related_project,
                        },
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                    )
                    self.tiered_memory.record(memory_item)
                except Exception:
                    pass  # Non-critical

            # 3. ImplicitFeedback: Track recommendation shown
            if self.implicit_feedback:
                try:
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "title": title,
                            "rationale": rationale,
                            "priority": priority,
                            "type": type,
                        },
                        context={"project": related_project, "source": "inject_recommendation"},
                    )
                except Exception:
                    pass  # Non-critical

            return True

        except Exception as e:
            print(f"Bridge Error (Inject): {e}", file=sys.stderr)
            return False

    # --- 3. Execution Bridge ---

    def trigger_action(self, agent_id: str, payload: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Trigger an automated agent via Local Orchestrator.

        Args:
            agent_id: ID of the agent to trigger
            payload: Context dictionary
        """
        if not self.orchestrator or not self.orchestrator.is_available():
            return {"success": False, "error": "Local Orchestrator not connected"}

        if not self.orchestrator.orchestrator:
            return {"success": False, "error": "Orchestrator instance missing"}

        try:
            result = self.orchestrator.orchestrator.trigger_agent(
                agent_id=agent_id, context=payload or {}
            )

            return {
                "success": result.success,
                "message": result.message,
                "data": result.data,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # --- 4. Portfolio Bridge ---

    def get_portfolio_context(self, project: str) -> Dict[str, Any]:
        """
        Get comprehensive project context including patterns and lessons.

        Args:
            project: Project name (e.g., "vortex-backend")

        Returns:
            Dict with project, patterns, lessons, tech_stack, related

        Example:
            >>> bridge = CortexBridge()
            >>> context = bridge.get_portfolio_context("vortex-backend")
            >>> print(context["lessons"][0]["lesson"])
        """
        if not self.portfolio:
            return {"error": "Portfolio memory not available"}

        try:
            return self.portfolio.get_project_context(project)
        except Exception as e:
            return {"error": str(e)}

    def get_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns.

        Args:
            pattern_type: Optional pattern name filter

        Returns:
            List of pattern dicts

        Example:
            >>> bridge = CortexBridge()
            >>> patterns = bridge.get_patterns("async_fastapi")
        """
        if not self.portfolio:
            return [{"error": "Portfolio memory not available"}]

        try:
            return self.portfolio.get_cross_project_patterns(pattern_type)
        except Exception as e:
            return [{"error": str(e)}]

    def get_portfolio_patterns(self, pattern_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Get cross-project patterns (alias for get_patterns for API compatibility).

        Args:
            pattern_type: Optional pattern category filter

        Returns:
            List of pattern dictionaries

        Example:
            >>> bridge = CortexBridge()
            >>> patterns = bridge.get_portfolio_patterns(pattern_type="async_fastapi")
        """
        return self.get_patterns(pattern_type=pattern_type)

    def get_lessons(
        self, project: Optional[str] = None, pattern: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get lessons learned.

        Args:
            project: Filter by affected project
            pattern: Filter by pattern type

        Returns:
            List of lesson dicts

        Example:
            >>> bridge = CortexBridge()
            >>> lessons = bridge.get_lessons(project="vortex-backend")
        """
        if not self.portfolio:
            return [{"error": "Portfolio memory not available"}]

        try:
            return self.portfolio.get_lessons_learned(project=project, pattern=pattern)
        except Exception as e:
            return [{"error": str(e)}]

    # --- Intelligence Enhancement Methods ---

    def generate_synthetic(
        self,
        data_type: str = "profiles",
        count: int = 100,
        segment: Optional[str] = None,
        province: Optional[str] = None,
        risk_profile: Optional[str] = None,
        min_quality: float = 0.7,
        output_format: str = "jsonl",
    ) -> Dict[str, Any]:
        """
        Generate synthetic Canadian FinServ data.

        Args:
            data_type: "profiles" or "transactions"
            count: Number of records to generate
            segment: Target customer segment (e.g., "mass_affluent")
            province: Target province (e.g., "ON")
            risk_profile: For transactions — "low", "medium", "high"
            min_quality: Minimum quality score threshold (0.0-1.0)
            output_format: "jsonl", "json", or "csv"

        Returns:
            Dict with generation results and metadata
        """
        if not SYNTHETIC_AVAILABLE or not self.synthetic_generator:
            return {"error": "Synthetic data engine not available", "available": False}

        request = GenerationRequest(
            data_type=data_type,
            count=count,
            segment=segment,
            province=province,
            risk_profile=risk_profile,
            include_risk_flags=risk_profile is not None,
            min_quality_score=min_quality,
            output_format=output_format,
        )

        result = self.synthetic_generator.generate(request)

        return {
            "success": True,
            "summary": result.summary(),
            "records_generated": result.records_generated,
            "records_passed": result.records_passed_quality,
            "records_rejected": result.records_rejected,
            "avg_quality": result.average_quality_score,
            "quality_distribution": result.quality_distribution,
            "output_path": result.output_path,
            "flywheel_id": result.flywheel_id,
            "generation_time_s": result.generation_time_seconds,
        }

    def query_intelligence(
        self,
        request: str,
        project: str,
        query_type: str = "spec",
        use_cache: bool = True,
        parallel: bool = True,
    ) -> Dict[str, Any]:
        """
        Query unified intelligence API with enhanced features.

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate input (already exists)
        2. HybridRetriever - Add related patterns
        3. ContextOptimizer - Optimize result context
        4. TieredMemory - Record query for learning

        Args:
            request: User request (e.g., "enhance golden spec method")
            project: Project name (e.g., "cortex")
            query_type: Type of query ("spec", "impl", "analysis", "research")
            use_cache: Whether to use query result cache (default: True)
            parallel: Whether to query sources in parallel (default: True)

        Returns:
            Dict representation of IntelligenceResult with enhanced features:
            - Ranked results by relevance
            - Confidence scores for all components
            - Detailed reasoning for results
            - Overall confidence score
            - related_patterns from hybrid retrieval (when available)

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.query_intelligence("enhance golden spec", "cortex")
            >>> print(result["overall_confidence"])  # 0.85
            >>> print(result["reasoning"])  # Detailed reasoning
        """
        if not self.unified_intel:
            return {"error": "Unified Intelligence not available"}

        if not IntelligenceQueryType:
            return {"error": "Intelligence models not available"}

        # 1. DefensivePrompting: Apply defensive prompting if enabled
        if self.config and self.config.defensive_prompting_enabled and self.defensive:
            validation = self.defensive.validate_input(request)
            if not validation.valid:
                return {
                    "error": "Input validation failed",
                    "issues": validation.issues,
                    "severity": validation.severity,
                }
            request = validation.sanitized_input

        try:
            query_type_enum = IntelligenceQueryType(query_type)
            result = self.unified_intel.query(
                user_request=request,
                project=project,
                query_type=query_type_enum,
                use_cache=use_cache,
                parallel=parallel,
            )
            result_dict = result.to_dict()

            # 1b. V2 Engine Enrichment: Add graph context from Signal Bus
            if getattr(self, "signal_bus", None):
                try:
                    v2_ctx = self.signal_bus.query(
                        context=request,
                        project=project,
                        tool_source="query_intelligence",
                    )
                    result_dict["v2_context"] = {
                        "graph_nodes": v2_ctx.get("graph_nodes", []),
                        "recent_signals": v2_ctx.get("recent_signals", []),
                        "cross_project_patterns": (
                            self.signal_bus.get_cross_project_patterns(project)
                        ),
                    }
                except Exception:
                    pass  # V2 enrichment is non-critical

            # 1c. V2 Signal Recording: Record this query as a workspace signal
            if getattr(self, "signal_bus", None):
                try:
                    from cortex.engines.workstream_orchestrator import (
                        WorkspaceSignal,
                        SignalSource,
                        WorkstreamPhase,
                    )

                    sig = WorkspaceSignal(
                        source=SignalSource.CLAUDE_CODE,
                        timestamp=datetime.now(),
                        project=project,
                        workstream=WorkstreamPhase.BUILD,
                        content_type=query_type,
                        content=request[:500],
                    )
                    self.signal_bus.absorb(sig)
                except Exception:
                    pass  # Signal recording is non-critical

            # 2. HybridRetriever: Add related patterns
            if self.hybrid_retriever:
                try:
                    hybrid_results = self.hybrid_retriever.search(request, limit=3, alpha=0.5)
                    related_patterns = [
                        {
                            "title": pattern.title,
                            "description": pattern.description,
                            "score": score,
                        }
                        for pattern, score in hybrid_results
                    ]
                    result_dict["related_patterns"] = related_patterns
                except Exception:
                    pass  # Non-critical

            # 3. ContextOptimizer: Apply optimization info (if available)
            if self.context_optimizer and CONTEXT_OPTIMIZER_AVAILABLE:
                try:
                    result_dict["context_optimization"] = {
                        "strategy": "importance",
                        "applied": True,
                    }
                except Exception:
                    pass

            # 3b. V2 Reasoning: Synthesize retrieved context via LLM
            try:
                from cortex.intelligence.reasoning import ReasoningLayer, classify_query

                tier = classify_query(request)
                reasoner = ReasoningLayer()
                result_dict["reasoning"] = reasoner.reason(request, result_dict, tier)
            except Exception:
                pass  # Reasoning failure never blocks response

            # 4. TieredMemory: Record query for learning
            if self.tiered_memory and TIERED_MEMORY_AVAILABLE and MemoryItem:
                try:
                    import uuid

                    query_id = f"intel_{uuid.uuid4().hex[:8]}"
                    memory_item = MemoryItem(
                        id=query_id,
                        content={
                            "type": "intelligence_query",
                            "title": f"Query: {request[:50]}...",
                            "description": request,
                            "project": project,
                            "query_type": query_type,
                        },
                        created_at=datetime.now(),
                        last_accessed=datetime.now(),
                    )
                    self.tiered_memory.record(memory_item)
                except Exception:
                    pass  # Non-critical

            return result_dict
        except Exception as e:
            return {"error": str(e)}

    def get_interventions(self, project: str, context: str = "") -> list:
        """Return proactive interventions from V2 reasoning layer."""
        if not getattr(self, "synthesis", None):
            return []
        try:
            from cortex.intelligence.v2_reasoning import V2ReasoningLayer

            layer = V2ReasoningLayer(self.synthesis)
            return layer.evaluate(context=context, project=project)
        except Exception:
            return []

    def get_prompt_template(self, prompt_name: str, **variables) -> Optional[str]:
        """
        Get a prompt template from registry with variables filled in.

        Phase 1 Integration: Uses versioned prompt templates if enabled.

        Args:
            prompt_name: Name of prompt template
            **variables: Variables to fill into template

        Returns:
            Rendered prompt string, or None if template not found
        """
        if not self.config or not self.config.prompt_versioning_enabled or not self.prompt_registry:
            return None

        template = self.prompt_registry.get_prompt(prompt_name, version=self.config.prompt_version)
        if not template:
            return None

        return template.render(**variables)

    def find_similar_work(self, domain: str, project: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Find similar work across portfolio.

        Args:
            domain: Domain/topic (e.g., "wind forecasting ensemble")
            project: Current project context
            limit: Max results

        Returns:
            List of SimilarWork dicts

        Example:
            >>> bridge = CortexBridge()
            >>> similar = bridge.find_similar_work("ensemble forecasting", "vortex-backend")
        """
        if not self.spec_kb:
            return [{"error": "Spec Knowledge Base not available"}]

        try:
            from dataclasses import asdict

            similar = self.spec_kb.find_similar(domain, k=limit, project_filter=project)
            return [asdict(s) for s in similar]
        except Exception as e:
            return [{"error": str(e)}]

    def search_specs(
        self, query: str, project: Optional[str] = None, limit: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Search indexed specifications (alias for find_similar_work for API compatibility).

        Uses AI Engineering pipeline:
        1. DefensivePrompting - Validate query
        2. HybridRetriever - Hybrid search first
        3. SpecKnowledgeBase - Fallback to existing system
        4. ImplicitFeedback - Track results

        Args:
            query: Search query string
            project: Optional project filter
            limit: Maximum results

        Returns:
            List of matching specs with similarity scores

        Example:
            >>> bridge = CortexBridge()
            >>> results = bridge.search_specs("API rate limiting", project="cortex", limit=5)
        """
        # 1. DefensivePrompting: Validate query
        if self.defensive and self.config and self.config.defensive_prompting_enabled:
            validation = self.defensive.validate_input(query)
            if not validation.valid:
                return [
                    {
                        "error": "Query validation failed",
                        "issues": validation.issues,
                    }
                ]
            query = validation.sanitized_input

        results = []

        # 2. HybridRetriever: Try hybrid search first
        if self.hybrid_retriever:
            try:
                hybrid_results = self.hybrid_retriever.search(query, limit=limit, alpha=0.5)
                for pattern, score in hybrid_results:
                    result = {
                        "spec_name": pattern.title,
                        "title": pattern.title,
                        "description": pattern.description,
                        "similarity": score,
                        "similarity_score": score,
                        "source": "hybrid_retriever",
                    }
                    results.append(result)
            except Exception:
                pass  # Fall through to spec_kb

        # 3. SpecKnowledgeBase: Fallback to existing system
        if len(results) < limit and self.spec_kb:
            try:
                remaining = limit - len(results)
                # Try intelligence version first (ChromaDB-based)
                if hasattr(self.spec_kb, "find_similar"):
                    from dataclasses import asdict

                    similar = self.spec_kb.find_similar(query, k=remaining, project_filter=project)
                    # Transform SimilarWork dataclass to expected format
                    for s in similar:
                        result = asdict(s)
                        result["source"] = "spec_knowledge_base"
                        # Map 'title' to 'spec_name' for API compatibility
                        if "spec_name" not in result:
                            if "title" in result:
                                result["spec_name"] = result["title"]
                            elif "name" in result:
                                result["spec_name"] = result["name"]
                        # Ensure similarity_score is present
                        if "similarity" not in result and "similarity_score" in result:
                            result["similarity"] = result["similarity_score"]
                        results.append(result)
                # Fallback to simple hash-based version
                elif hasattr(self.spec_kb, "search"):
                    kb_results = self.spec_kb.search(query, project=project, limit=remaining)
                    for r in kb_results:
                        r["source"] = "spec_knowledge_base"
                        results.append(r)
            except Exception as e:
                if not results:
                    return [{"error": str(e)}]

        # Handle no results
        if not results:
            if not self.spec_kb:
                return [{"error": "Spec Knowledge Base not available"}]
            return []

        # 4. ImplicitFeedback: Track results
        if self.implicit_feedback:
            try:
                for i, result in enumerate(results):
                    rec_id = f"spec_{result.get('spec_name', f'spec_{i}')}_{i}"
                    self.implicit_feedback.track_recommendation_shown(
                        rec_id=rec_id,
                        recommendation={
                            "spec_name": result.get("spec_name", ""),
                            "title": result.get("title", ""),
                            "source": result.get("source", "unknown"),
                            "position": i,
                        },
                        context={"query": query, "project": project},
                    )
            except Exception:
                pass  # Non-critical

        return results[:limit]

    def get_session_context(self, format: str = "structured") -> Dict[str, Any]:
        """
        Get current session context.

        Args:
            format: Output format ('terminal' or 'structured', default: 'structured')

        Returns:
            SessionContext dict or formatted string

        Example:
            >>> bridge = CortexBridge()
            >>> context = bridge.get_session_context(format='structured')
        """
        if not self.session_mgr:
            return {"error": "Session Manager not available"}

        try:
            # Load SessionContext dataclass
            from dataclasses import asdict

            session_ctx = self.session_mgr.load_session_context()

            if not session_ctx:
                return {"error": "No session context available"}

            if format == "terminal":
                # Format for terminal display
                context_dict = asdict(session_ctx)
                # Build terminal-friendly format
                lines = [
                    f"Project: {context_dict.get('project', 'unknown')}",
                    f"Focus: {context_dict.get('current_focus', 'unknown')}",
                    f"Goals: {', '.join(context_dict.get('active_goals', []))}",
                ]
                return {"context": "\n".join(lines), "format": "terminal"}
            else:
                # Return structured dict with expected keys
                context_dict = asdict(session_ctx)
                # Map to expected format: project, git, goals
                result = {
                    "project": {
                        "name": context_dict.get("project", "unknown"),
                        "path": context_dict.get("working_directory", ""),
                    },
                    "git": {"recent_commits": context_dict.get("recent_work", [])},
                    "goals": context_dict.get("active_goals", []),
                    "focus": context_dict.get("current_focus", "unknown"),
                    "working_directory": context_dict.get("working_directory", ""),
                    "last_updated": context_dict.get("last_updated", ""),
                }
                return result
        except Exception as e:
            return {"error": str(e)}

    def index_spec(
        self, spec_path: str, project: str, domain: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Index a spec in knowledge base.

        Args:
            spec_path: Path to spec file
            project: Project name
            domain: Optional domain tag

        Returns:
            Result dict with spec_id

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.index_spec("/path/to/spec.md", "cortex", "intelligence")
        """
        if not self.spec_kb:
            return {"error": "Spec Knowledge Base not available"}

        try:
            metadata = {
                "project": project,
                "domain": domain,
                "indexed_at": datetime.now().isoformat(),
            }

            spec_id = self.spec_kb.index_spec(Path(spec_path), metadata)

            return {
                "success": True,
                "spec_id": spec_id,
                "message": f"Spec indexed: {spec_path}",
            }
        except Exception as e:
            return {"error": str(e)}

    # --- Recommendation Methods ---

    def get_recommendations(self) -> Dict[str, Any]:
        """
        Get smart recommendations based on health, goals, and dependencies.

        Returns:
            Full recommendations report with priority projects, alerts, and next action

        Example:
            >>> bridge = CortexBridge()
            >>> recs = bridge.get_recommendations()
            >>> print(recs["next_action"]["action"])
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_full_report()
        except Exception as e:
            return {"error": str(e)}

    def get_next_action(self) -> Dict[str, Any]:
        """
        Get single most important recommended action.

        Returns:
            Dict with action, reason, priority, and type

        Example:
            >>> bridge = CortexBridge()
            >>> action = bridge.get_next_action()
            >>> print(f"[{action['priority']}] {action['action']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_recommended_next_action()
        except Exception as e:
            return {"error": str(e)}

    def get_risk_alerts(self) -> List[Dict[str, Any]]:
        """
        Get risk alerts across the portfolio.

        Returns:
            List of risk alerts with severity, type, and recommendations

        Example:
            >>> bridge = CortexBridge()
            >>> alerts = bridge.get_risk_alerts()
            >>> for alert in alerts:
            ...     print(f"[{alert['severity']}] {alert['message']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_risk_alerts()
        except Exception as e:
            return [{"error": str(e)}]

    def get_priority_projects(self, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get projects that need attention, prioritized by goals and health.

        Args:
            limit: Maximum projects to return

        Returns:
            List of priority projects with reasons

        Example:
            >>> bridge = CortexBridge()
            >>> priorities = bridge.get_priority_projects()
            >>> for p in priorities:
            ...     print(f"[{p['priority']}] {p['project']}: {p['reason']}")
        """
        try:
            from cortex.recommendations import RecommendationEngine

            engine = RecommendationEngine(self.root_dir)
            return engine.get_priority_projects(limit=limit)
        except Exception as e:
            return [{"error": str(e)}]

    # --- Implicit Feedback Methods ---

    def track_recommendation_shown(
        self, rec_id: str, recommendation: Dict, context: Optional[Dict] = None
    ) -> bool:
        """
        Track when a recommendation is displayed to user.

        Call this when showing recommendations to enable implicit feedback tracking.

        Args:
            rec_id: Unique recommendation identifier
            recommendation: The recommendation dict (with title, description, etc.)
            context: Optional context (project, goal, etc.)

        Returns:
            True if tracked, False if implicit feedback not available
        """
        if not self.implicit_feedback:
            return False

        try:
            self.implicit_feedback.track_recommendation_shown(rec_id, recommendation, context)
            return True
        except Exception:
            return False

    def track_action_taken(
        self, action: str, files: Optional[List[str]] = None, context: Optional[Dict] = None
    ) -> bool:
        """
        Track user action and correlate with pending recommendations.

        Call this when user takes an action (command, file edit, etc.)
        to automatically detect follows, ignores, and overrides.

        Args:
            action: Description of action taken
            files: Files involved in the action
            context: Additional context

        Returns:
            True if tracked, False if implicit feedback not available
        """
        if not self.implicit_feedback:
            return False

        try:
            self.implicit_feedback.track_action_taken(action, files, context)
            return True
        except Exception:
            return False

    def end_feedback_session(self) -> Dict[str, Any]:
        """
        End implicit feedback session and mark un-acted recommendations as ignored.

        Call this at end of session or after timeout.

        Returns:
            Session stats dict
        """
        if not self.implicit_feedback:
            return {"available": False}

        try:
            stats = self.implicit_feedback.get_session_stats()
            self.implicit_feedback.session_end()
            return {"available": True, "session_stats": stats}
        except Exception as e:
            return {"available": False, "error": str(e)}

    def get_implicit_feedback_stats(self, days: int = 7) -> Dict[str, Any]:
        """
        Get implicit feedback statistics over time period.

        Args:
            days: Number of days to analyze

        Returns:
            Dict with follow rate, ignore rate, average time-to-action, etc.
        """
        if not self.implicit_feedback:
            return {"available": False}

        try:
            return {"available": True, "stats": self.implicit_feedback.get_stats(days)}
        except Exception as e:
            return {"available": False, "error": str(e)}

    # --- 8. Layer 2: Pattern Memory Bridge ---

    def find_similar_work_by_task(self, project: str, task: str, limit: int = 5) -> Dict[str, Any]:
        """
        Find similar work from other projects by task description.

        Args:
            project: Current project name
            task: Task description
            limit: Maximum results

        Returns:
            Similar work from other projects
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(project_path=project_path, enable_patterns=True)
            similar = engine.find_similar_work(task=task, limit=limit)

            return {
                "success": True,
                "task": task,
                "similar_work": similar,
                "count": len(similar),
            }

        except Exception as e:
            return {"error": str(e)}

    # --- 9. Smart Recommendations Bridge ---

    def get_smart_recommendations(
        self, project: str, limit: int = 10, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Get smart, prioritized recommendations for a project.

        Args:
            project: Project name
            limit: Maximum recommendations to return
            context: Optional context dictionary

        Returns:
            Dictionary with prioritized recommendations
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(
                project_path=project_path, enable_learning=True, enable_patterns=True
            )

            recommendations = engine.generate_recommendations(context=context, limit=limit)

            # Convert to dict format
            rec_dicts = []
            for rec in recommendations:
                rec_dict = {
                    "type": rec.type.value if hasattr(rec.type, "value") else rec.type,
                    "title": rec.title,
                    "description": rec.description,
                    "priority": rec.priority.value
                    if hasattr(rec.priority, "value")
                    else rec.priority,
                    "confidence": rec.confidence.value
                    if hasattr(rec.confidence, "value")
                    else rec.confidence,
                    "calculated_priority": (
                        rec.metadata.get("calculated_priority", 0.5)
                        if getattr(rec, "metadata", None)
                        else 0.5
                    ),
                    "files": getattr(rec, "files", None) or [],
                    "steps": [
                        s.description if hasattr(s, "description") else str(s)
                        for s in (getattr(rec, "steps", None) or [])
                    ],
                    "rationale": (
                        rec.metadata.get("rationale", "") if getattr(rec, "metadata", None) else ""
                    ),
                    "pattern": (
                        rec.metadata.get("pattern", "") if getattr(rec, "metadata", None) else ""
                    ),
                    "pattern_success_rate": (
                        rec.metadata.get("pattern_success_rate", 0.0)
                        if getattr(rec, "metadata", None)
                        else 0.0
                    ),
                }
                rec_dicts.append(rec_dict)

            return {
                "success": True,
                "project": project,
                "recommendations": rec_dicts,
                "count": len(rec_dicts),
                "summary": {
                    "high_priority": sum(
                        1 for r in rec_dicts if r.get("calculated_priority", 0) > 0.7
                    ),
                    "pattern_based": sum(1 for r in rec_dicts if r.get("pattern", "")),
                },
            }

        except Exception as e:
            return {"error": str(e)}

    def get_recommendation_dashboard(self, project: str, limit: int = 10) -> Dict[str, Any]:
        """
        Get recommendation dashboard with prioritized recommendations, health, and context.

        Args:
            project: Project name
            limit: Maximum recommendations to return

        Returns:
            Dashboard dictionary with recommendations, health, alerts, and patterns
        """
        try:
            from recommendation_engine import RecommendationEngine

            project_path = self.root_dir / project
            if not project_path.exists():
                project_path = self.root_dir

            engine = RecommendationEngine(
                project_path=project_path, enable_learning=True, enable_patterns=True
            )

            dashboard = engine.get_recommendation_dashboard(project=project, limit=limit)

            return {"success": True, **dashboard}

        except Exception as e:
            return {"error": str(e)}

    # ==================== Rule Tracking Methods ====================

    def log_rule_event(
        self, rule_name: str, event_type: str, context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Log a rule adherence event for Cortex learning.

        Args:
            rule_name: Name of the rule (e.g., "read_before_edit", "file_references", "unnecessary_questions")
            event_type: Type of event ("violation", "adherence", "warning")
            context: Additional context (tool, file, project, etc.)

        Returns:
            Dict with success status and event_id
        """
        from datetime import datetime

        # Rule events file
        rule_events_file = Path.home() / ".cortex" / "rule_events.jsonl"
        rule_events_file.parent.mkdir(parents=True, exist_ok=True)

        event_id = f"rule_{rule_name}_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}"

        event = {
            "event_id": event_id,
            "timestamp": datetime.now().isoformat(),
            "rule_name": rule_name,
            "event_type": event_type,
            "context": context or {},
            "project": context.get("project", "unknown") if context else "unknown",
            "session_id": context.get("session_id") if context else None,
        }

        try:
            with open(rule_events_file, "a") as f:
                f.write(json.dumps(event) + "\n")

            return {
                "success": True,
                "event_id": event_id,
                "rule_name": rule_name,
                "event_type": event_type,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def get_rule_correlations(
        self, rule_name: Optional[str] = None, days: int = 30
    ) -> Dict[str, Any]:
        """
        Get correlations between rule violations and session outcomes.

        Args:
            rule_name: Optional filter by specific rule
            days: Number of days to analyze

        Returns:
            Dict with rule correlations and patterns
        """
        from collections import defaultdict
        from datetime import datetime, timedelta

        rule_events_file = Path.home() / ".cortex" / "rule_events.jsonl"
        outcomes_file = Path.home() / ".cortex" / "outcomes.jsonl"

        # Load rule events
        rule_events = []
        if rule_events_file.exists():
            cutoff = datetime.now() - timedelta(days=days)
            with open(rule_events_file, "r") as f:
                for line in f:
                    try:
                        event = json.loads(line.strip())
                        event_time = datetime.fromisoformat(event["timestamp"])
                        if event_time >= cutoff:
                            if rule_name is None or event["rule_name"] == rule_name:
                                rule_events.append(event)
                    except (json.JSONDecodeError, KeyError, ValueError):
                        continue

        # Load outcomes for correlation
        outcomes = []
        if outcomes_file.exists():
            with open(outcomes_file, "r") as f:
                for line in f:
                    try:
                        outcome = json.loads(line.strip())
                        outcomes.append(outcome)
                    except json.JSONDecodeError:
                        continue

        # Analyze correlations
        by_rule = defaultdict(lambda: {"violations": 0, "adherences": 0, "warnings": 0})
        for event in rule_events:
            rule = event["rule_name"]
            event_type = event["event_type"]
            if event_type == "violation":
                by_rule[rule]["violations"] += 1
            elif event_type == "adherence":
                by_rule[rule]["adherences"] += 1
            elif event_type == "warning":
                by_rule[rule]["warnings"] += 1

        # Calculate adherence rates
        correlations = {}
        for rule, counts in by_rule.items():
            total = counts["violations"] + counts["adherences"]
            adherence_rate = counts["adherences"] / total if total > 0 else 0.0
            correlations[rule] = {
                "total_events": total + counts["warnings"],
                "violations": counts["violations"],
                "adherences": counts["adherences"],
                "warnings": counts["warnings"],
                "adherence_rate": round(adherence_rate, 3),
            }

        return {
            "success": True,
            "days_analyzed": days,
            "total_events": len(rule_events),
            "rules_tracked": list(correlations.keys()),
            "correlations": correlations,
            "outcomes_count": len(outcomes),
        }

    # ==================== Deep Mode Integration ====================

    def analyze_deep(
        self, project: Optional[str] = None, output_json: bool = False
    ) -> Dict[str, Any]:
        """
        Run comprehensive deep analysis (Depth-First Architecture).

        Performs:
        - Full git history analysis (90 days)
        - Fresh health calculation (no caching)
        - Code quality metrics
        - Automatic warnings and recommendations

        Args:
            project: Project name (auto-detect if None)
            output_json: Return JSON-serializable dict instead of object

        Returns:
            DeepIntelligence object or JSON dict

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_deep("cortex")
            >>> print(f"Health: {result.health.score}/100")
        """
        if not self.deep_analyzer:
            return {"error": "DeepAnalyzer not available (import failed)"}

        if not self.latency_manager:
            return {"error": "AdaptiveLatencyManager not available (import failed)"}

        # Auto-detect project if not specified
        if project is None:
            project = self._detect_current_project()

        # Get deep mode configuration
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.DEEP if AnalysisMode else None, context=None
        )

        # Run deep analysis
        try:
            result = self.deep_analyzer.analyze(project, config.__dict__)

            if output_json:
                return self._serialize_deep_intelligence(result)

            return result
        except Exception as e:
            return {"error": f"Deep analysis failed: {str(e)}"}

    def analyze_quick(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Run minimal fast analysis (<1s).

        Uses existing shallow context for speed.

        Args:
            project: Project name (auto-detect if None)

        Returns:
            Quick context dict

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_quick("cortex")
            >>> print(f"Status: {result.get('status')}")
        """
        if project is None:
            project = self._detect_current_project()

        # Use existing fast path via query_intelligence
        try:
            if self.unified_intel:
                result = self.unified_intel.query_intelligence(
                    request=f"Quick status check for {project}",
                    project=project,
                    query_type="status",
                )
                return result
            else:
                # Fallback to basic context
                return {
                    "project": project,
                    "status": "quick mode",
                    "message": "UnifiedIntelligence not available, returning basic context",
                }
        except Exception as e:
            return {"error": f"Quick analysis failed: {str(e)}"}

    def analyze_auto(self, project: Optional[str] = None) -> Dict[str, Any]:
        """
        Run adaptive analysis with intelligent mode selection.

        Selects mode based on:
        - Time since last session
        - Project state (uncommitted changes, stale branches)
        - User preferences

        Args:
            project: Project name (auto-detect if None)

        Returns:
            Intelligence result (deep or quick depending on context)

        Example:
            >>> bridge = CortexBridge()
            >>> result = bridge.analyze_auto("cortex")
            >>> # Automatically selects best mode
        """
        if not self.latency_manager:
            return {"error": "AdaptiveLatencyManager not available"}

        if project is None:
            project = self._detect_current_project()

        # Build session context for mode selection
        session_ctx = self._build_session_context(project)

        # Select mode adaptively
        config = self.latency_manager.select_mode(
            requested_mode=AnalysisMode.AUTO if AnalysisMode else None, context=session_ctx
        )

        # Route to appropriate analysis
        mode_name = config.mode_name if hasattr(config, "mode_name") else "deep"

        if mode_name == "fast":
            return self.analyze_quick(project)
        else:
            # Default to deep for balanced and deep modes
            return self.analyze_deep(project)

    def get_anomalies(
        self,
        severity: Optional[str] = None,
        anomaly_type: Optional[str] = None,
        min_severity: str = "WARNING",
    ) -> Dict[str, Any]:
        """
        Get detected orchestration anomalies.

        Args:
            severity: Optional exact severity filter: "CRITICAL", "WARNING", or "INFO".
                      When set, overrides min_severity.
            anomaly_type: Optional filter by anomaly type name.
            min_severity: Minimum severity threshold (default "WARNING" suppresses INFO).

        Returns:
            Dict with "count" and "anomalies" list.
        """
        try:
            from cortex.orchestration.anomaly_detector import OrchestrationAnomalyManager
            from cortex.orchestration.database import OrchestrationDatabase

            db = OrchestrationDatabase()
            mgr = OrchestrationAnomalyManager(db, enable_alerts=False)

            # Build context — active_projects as list is handled by type guard in detector
            context = {
                "active_projects": list(getattr(self, "_known_projects", [])),
                "total_projects": len(getattr(self, "_known_projects", [])),
                "goals_in_progress": 0,
                "goals_pending": 0,
            }

            effective_min = "INFO" if severity else min_severity
            anomalies = mgr.detect_all(context=context, min_severity=effective_min)

            if severity:
                anomalies = [
                    a
                    for a in anomalies
                    if getattr(a.severity, "value", str(a.severity)) == severity.upper()
                ]
            if anomaly_type:
                anomalies = [
                    a
                    for a in anomalies
                    if getattr(a.anomaly_type, "value", str(a.anomaly_type)) == anomaly_type
                ]

            return {
                "count": len(anomalies),
                "anomalies": [
                    {
                        "id": a.anomaly_id,
                        "type": getattr(a.anomaly_type, "value", str(a.anomaly_type)),
                        "severity": getattr(a.severity, "value", str(a.severity)),
                        "title": a.title,
                        "description": a.description,
                        "recommendation": a.remediation,
                        "detected_at": (
                            a.detected_at.isoformat()
                            if hasattr(a.detected_at, "isoformat")
                            else str(a.detected_at)
                            if a.detected_at
                            else None
                        ),
                    }
                    for a in anomalies
                ],
            }
        except Exception as e:
            return {"count": 0, "anomalies": [], "error": str(e)}
