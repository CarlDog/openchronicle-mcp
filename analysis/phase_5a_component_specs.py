"""
PHASE 5A COMPONENT SPECIFICATIONS

Date: August 4, 2025
Purpose: Detailed specifications for each component in the modular content analysis system
Status: Day 1 planning complete

=============================================================================
COMPONENT SPECIFICATIONS & INTERFACES
=============================================================================
"""

# SHARED INTERFACES AND BASE CLASSES
shared_interfaces = """
# core/content_analysis/shared/interfaces.py

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional

class ContentAnalysisComponent(ABC):
    \"\"\"Base interface for all content analysis components.\"\"\"
    
    def __init__(self, model_manager):
        self.model_manager = model_manager
    
    @abstractmethod
    async def process(self, content: str, context: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Process content and return analysis results.\"\"\"
        pass

class DetectionComponent(ContentAnalysisComponent):
    \"\"\"Base for content detection components.\"\"\"
    
    @abstractmethod
    def detect_content_type(self, content: str) -> Dict[str, Any]:
        \"\"\"Detect content type and classification.\"\"\"
        pass

class ExtractionComponent(ContentAnalysisComponent):
    \"\"\"Base for data extraction components.\"\"\"
    
    @abstractmethod
    async def extract_data(self, content: str) -> Dict[str, Any]:
        \"\"\"Extract structured data from content.\"\"\"
        pass

class RoutingComponent(ContentAnalysisComponent):
    \"\"\"Base for routing and recommendation components.\"\"\"
    
    @abstractmethod
    def get_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Get routing recommendation based on analysis.\"\"\"
        pass
"""

# DETECTION COMPONENTS
detection_components = {
    "content_classifier.py": {
        "purpose": "Main content type detection and classification",
        "class_name": "ContentClassifier",
        "methods": {
            "detect_content_type": "Main public API for content detection",
            "analyze_content_category": "Categorize content for import processing",
            "_combine_analysis_results": "Merge keyword and transformer results"
        },
        "dependencies": ["KeywordDetector", "TransformerAnalyzer"],
        "interface": """
class ContentClassifier(DetectionComponent):
    def __init__(self, model_manager, keyword_detector, transformer_analyzer):
        super().__init__(model_manager)
        self.keyword_detector = keyword_detector
        self.transformer_analyzer = transformer_analyzer
    
    def detect_content_type(self, user_input: str) -> Dict[str, Any]:
        \"\"\"Detect content type using combined analysis.\"\"\"
        
    async def analyze_content_category(self, content: str) -> Dict[str, Any]:
        \"\"\"Analyze content category for import processing.\"\"\"
        
    def _combine_analysis_results(self, keyword_analysis: Dict[str, Any], 
                                transformer_analysis: Dict[str, Any], 
                                user_input: str) -> Dict[str, Any]:
        \"\"\"Combine keyword and transformer analysis results.\"\"\"
        """
    },
    
    "keyword_detector.py": {
        "purpose": "Keyword-based content analysis and detection",
        "class_name": "KeywordDetector", 
        "methods": {
            "_keyword_based_detection": "Core keyword detection logic",
            "_basic_content_analysis": "Basic content analysis fallback"
        },
        "dependencies": [],
        "interface": """
class KeywordDetector(DetectionComponent):
    def __init__(self, model_manager):
        super().__init__(model_manager)
        self._initialize_keywords()
    
    def _keyword_based_detection(self, user_input: str) -> Dict[str, Any]:
        \"\"\"Perform keyword-based content detection.\"\"\"
        
    def _basic_content_analysis(self, content: str) -> Dict[str, Any]:
        \"\"\"Basic content analysis using keywords.\"\"\"
        
    def _initialize_keywords(self):
        \"\"\"Initialize keyword patterns and categories.\"\"\"
        """
    },
    
    "transformer_analyzer.py": {
        "purpose": "ML-based content analysis using transformers",
        "class_name": "TransformerAnalyzer",
        "methods": {
            "_analyze_with_transformers": "Core transformer analysis",
            "_initialize_transformers": "Initialize transformer models",
            "check_transformer_connectivity": "Check transformer availability"
        },
        "dependencies": ["transformers (optional)"],
        "interface": """
class TransformerAnalyzer(DetectionComponent):
    def __init__(self, model_manager, use_transformers: bool = True):
        super().__init__(model_manager)
        self.use_transformers = use_transformers and TRANSFORMERS_AVAILABLE
        if self.use_transformers:
            self._initialize_transformers()
    
    def _analyze_with_transformers(self, user_input: str) -> Dict[str, Any]:
        \"\"\"Analyze content using transformer models.\"\"\"
        
    def _initialize_transformers(self):
        \"\"\"Initialize transformer models safely.\"\"\"
        
    def check_transformer_connectivity(self) -> Dict[str, Any]:
        \"\"\"Check transformer connectivity and availability.\"\"\"
        """
    }
}

# EXTRACTION COMPONENTS
extraction_components = {
    "character_extractor.py": {
        "purpose": "Extract character data from content",
        "class_name": "CharacterExtractor",
        "methods": {
            "extract_character_data": "Extract character information from content",
            "extract_characters": "Extract character list for import processing"
        },
        "dependencies": ["AnalysisPipeline"],
        "interface": """
class CharacterExtractor(ExtractionComponent):
    def __init__(self, model_manager, analysis_pipeline):
        super().__init__(model_manager)
        self.analysis_pipeline = analysis_pipeline
    
    async def extract_character_data(self, content: str) -> Dict[str, Any]:
        \"\"\"Extract detailed character data from content.\"\"\"
        
    async def extract_characters(self, content: str, content_name: str) -> List[Dict[str, Any]]:
        \"\"\"Extract character list for import processing.\"\"\"
        """
    },
    
    "location_extractor.py": {
        "purpose": "Extract location data from content",
        "class_name": "LocationExtractor",
        "methods": {
            "extract_location_data": "Extract location information from content"
        },
        "dependencies": ["AnalysisPipeline"],
        "interface": """
class LocationExtractor(ExtractionComponent):
    def __init__(self, model_manager, analysis_pipeline):
        super().__init__(model_manager)
        self.analysis_pipeline = analysis_pipeline
    
    async def extract_location_data(self, content: str) -> Dict[str, Any]:
        \"\"\"Extract detailed location data from content.\"\"\"
        """
    },
    
    "lore_extractor.py": {
        "purpose": "Extract lore and metadata from content",
        "class_name": "LoreExtractor",
        "methods": {
            "extract_lore_data": "Extract lore information from content",
            "generate_import_metadata": "Generate metadata for imported content"
        },
        "dependencies": ["AnalysisPipeline"],
        "interface": """
class LoreExtractor(ExtractionComponent):
    def __init__(self, model_manager, analysis_pipeline):
        super().__init__(model_manager)
        self.analysis_pipeline = analysis_pipeline
    
    async def extract_lore_data(self, content: str) -> Dict[str, Any]:
        \"\"\"Extract lore and world-building data from content.\"\"\"
        
    async def generate_import_metadata(self, all_content: List[str], storypack_name: str) -> Dict[str, Any]:
        \"\"\"Generate comprehensive metadata for imported content.\"\"\"
        """
    }
}

# ROUTING COMPONENTS
routing_components = {
    "model_selector.py": {
        "purpose": "Intelligent model selection for content analysis",
        "class_name": "ModelSelector",
        "methods": {
            "get_best_analysis_model": "Select best model for analysis task",
            "_check_model_suitability": "Check if model is suitable for content type",
            "test_model_availability": "Test if model is available and working",
            "find_working_analysis_models": "Find all working models for content type"
        },
        "dependencies": [],
        "interface": """
class ModelSelector(RoutingComponent):
    def __init__(self, model_manager):
        super().__init__(model_manager)
    
    def get_best_analysis_model(self, content_type: str = "general", allow_fallbacks: bool = True) -> str:
        \"\"\"Select the best model for analysis task.\"\"\"
        
    def _check_model_suitability(self, model_name: str, content_type: str) -> Dict[str, Any]:
        \"\"\"Check if model is suitable for content type.\"\"\"
        
    async def test_model_availability(self, model_name: str) -> Dict[str, Any]:
        \"\"\"Test if model is available and working.\"\"\"
        
    async def find_working_analysis_models(self, content_type: str = "analysis") -> List[Dict[str, Any]]:
        \"\"\"Find all working models for content type.\"\"\"
        """
    },
    
    "content_router.py": {
        "purpose": "Content-based routing logic",
        "class_name": "ContentRouter",
        "methods": {
            "get_routing_recommendation": "Get routing recommendation based on analysis",
            "recommend_generation_model": "Recommend model for content generation"
        },
        "dependencies": ["ModelSelector"],
        "interface": """
class ContentRouter(RoutingComponent):
    def __init__(self, model_manager, model_selector):
        super().__init__(model_manager)
        self.model_selector = model_selector
    
    def get_routing_recommendation(self, analysis: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Get routing recommendation based on content analysis.\"\"\"
        
    def recommend_generation_model(self, analysis: Dict[str, Any]) -> str:
        \"\"\"Recommend best model for content generation.\"\"\"
        """
    },
    
    "recommendation_engine.py": {
        "purpose": "Model recommendation and management suggestions",
        "class_name": "RecommendationEngine",
        "methods": {
            "_suggest_model_improvements": "Suggest model improvements",
            "_check_ollama_alternatives": "Check Ollama alternatives",
            "_provide_model_guidance": "Provide model guidance",
            "suggest_model_management_actions": "Suggest management actions",
            "_get_install_commands": "Get installation commands"
        },
        "dependencies": [],
        "interface": """
class RecommendationEngine(RoutingComponent):
    def __init__(self, model_manager):
        super().__init__(model_manager)
    
    def _suggest_model_improvements(self, content_type: str, unsuitable_models: List[tuple], fallback_models: List[tuple]):
        \"\"\"Suggest model improvements for content type.\"\"\"
        
    async def suggest_model_management_actions(self, content_type: str, system_resources: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        \"\"\"Suggest model management actions.\"\"\"
        """
    }
}

# SHARED COMPONENTS  
shared_components = {
    "analysis_pipeline.py": {
        "purpose": "Common analysis workflows and utilities",
        "class_name": "AnalysisPipeline",
        "methods": {
            "_build_analysis_prompt": "Build analysis prompt for models",
            "_parse_analysis_response": "Parse model analysis response",
            "_analyze_content_structure": "Analyze content structure"
        },
        "dependencies": [],
        "interface": """
class AnalysisPipeline:
    def __init__(self, model_manager):
        self.model_manager = model_manager
    
    def _build_analysis_prompt(self, user_input: str, story_context: Dict[str, Any]) -> str:
        \"\"\"Build analysis prompt for model processing.\"\"\"
        
    def _parse_analysis_response(self, response: str) -> Dict[str, Any]:
        \"\"\"Parse model analysis response into structured data.\"\"\"
        
    def _analyze_content_structure(self, content: str) -> Dict[str, Any]:
        \"\"\"Analyze content structure and patterns.\"\"\"
        """
    },
    
    "fallback_manager.py": {
        "purpose": "Analysis fallback handling and error recovery",
        "class_name": "FallbackManager",
        "methods": {
            "_basic_analysis_fallback": "Basic analysis fallback",
            "_fallback_analysis": "Generic fallback analysis"
        },
        "dependencies": [],
        "interface": """
class FallbackManager:
    def __init__(self, model_manager):
        self.model_manager = model_manager
    
    def _basic_analysis_fallback(self, user_input: str, story_context: Dict[str, Any], content_detection: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        \"\"\"Basic analysis fallback when models fail.\"\"\"
        
    def _fallback_analysis(self, user_input: str) -> Dict[str, Any]:
        \"\"\"Generic fallback analysis using heuristics.\"\"\"
        """
    },
    
    "metadata_processor.py": {
        "purpose": "Structured metadata handling and optimization",
        "class_name": "MetadataProcessor",
        "methods": {
            "optimize_canon_selection": "Optimize canon selection based on analysis",
            "optimize_memory_context": "Optimize memory context",
            "generate_content_flags": "Generate content flags"
        },
        "dependencies": [],
        "interface": """
class MetadataProcessor:
    def __init__(self, model_manager):
        self.model_manager = model_manager
    
    async def optimize_canon_selection(self, analysis: Dict[str, Any], story_data: Dict[str, Any]) -> List[str]:
        \"\"\"Optimize canon selection based on analysis.\"\"\"
        
    async def optimize_memory_context(self, analysis: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Optimize memory context for analysis.\"\"\"
        
    async def generate_content_flags(self, analysis: Dict[str, Any], response: str) -> List[Dict[str, Any]]:
        \"\"\"Generate content flags based on analysis.\"\"\"
        """
    }
}

# ORCHESTRATOR COMPONENT
orchestrator_spec = {
    "analyzer_orchestrator.py": {
        "purpose": "Main coordinator replacing ContentAnalyzer class",
        "class_name": "AnalyzerOrchestrator",
        "methods": {
            "__init__": "Initialize all components",
            "analyze_user_input": "Main user input analysis API",
            "analyze_imported_content": "Analyze imported content"
        },
        "dependencies": ["All detection, extraction, routing, and shared components"],
        "interface": """
class AnalyzerOrchestrator:
    \"\"\"Main content analysis orchestrator replacing ContentAnalyzer.\"\"\"
    
    def __init__(self, model_manager, use_transformers: bool = True):
        self.model_manager = model_manager
        
        # Initialize shared components
        self.analysis_pipeline = AnalysisPipeline(model_manager)
        self.fallback_manager = FallbackManager(model_manager)
        self.metadata_processor = MetadataProcessor(model_manager)
        
        # Initialize detection components
        self.keyword_detector = KeywordDetector(model_manager)
        self.transformer_analyzer = TransformerAnalyzer(model_manager, use_transformers)
        self.content_classifier = ContentClassifier(model_manager, self.keyword_detector, self.transformer_analyzer)
        
        # Initialize extraction components
        self.character_extractor = CharacterExtractor(model_manager, self.analysis_pipeline)
        self.location_extractor = LocationExtractor(model_manager, self.analysis_pipeline)
        self.lore_extractor = LoreExtractor(model_manager, self.analysis_pipeline)
        
        # Initialize routing components
        self.model_selector = ModelSelector(model_manager)
        self.content_router = ContentRouter(model_manager, self.model_selector)
        self.recommendation_engine = RecommendationEngine(model_manager)
    
    async def analyze_user_input(self, user_input: str, story_context: Dict[str, Any]) -> Dict[str, Any]:
        \"\"\"Main user input analysis API - backward compatible replacement.\"\"\"
        
    async def analyze_imported_content(self, content: str, content_name: str, analysis_type: str = "general") -> Dict[str, Any]:
        \"\"\"Analyze imported content - backward compatible replacement.\"\"\"
        """
    }
}

print("PHASE 5A COMPONENT SPECIFICATIONS COMPLETE")
print("=" * 60)
print("✅ Shared interfaces defined")
print("✅ Detection components specified (3 components)")
print("✅ Extraction components specified (3 components)")  
print("✅ Routing components specified (3 components)")
print("✅ Shared components specified (3 components)")
print("✅ Orchestrator component specified")
print()
print("📋 TOTAL: 13 focused components replacing 1 monolith")
print("🎯 READY FOR DAY 2: Component extraction begins")
print()
print("NEXT: Begin extraction of detection components")
print("- Create core/content_analysis/ directory structure")
print("- Extract KeywordDetector component")
print("- Extract TransformerAnalyzer component") 
print("- Extract ContentClassifier component")
print("- Validate detection functionality")
