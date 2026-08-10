import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.script_parsing_service import script_parsing_service
import re

def test_script_parsing_with_sample():
    """Test our script parsing with a sample script that has the issue"""
    
    # This is the problematic output from the issue
    sample_script = '''**Title: "Ecology's Groundbreaking Discoveries in 2025"**
**Full Narrative:**
Ecology advances rapidly with groundbreaking discoveries in 2025. Scientists reveal the true impact of microplastics on marine life, showing how these tiny pollutants disrupt entire food chains. Nature's resilience shines as researchers document coral reefs and forests regenerating in unexpected ways. Climate change insights deepen as experts uncover new patterns in polar ice cap melting and its global effects. Biodiversity thrives in hotspots as explorers find new species in the Amazon and other rich ecosystems. Urban ecology breakthroughs transform city planning with green infrastructure that supports wildlife. Human actions have consequences, but also solutions emerge through global conservation efforts. Sustainable futures are possible as renewable energy and eco-friendly technologies become mainstream. Global cooperation is key as nations unite for environmental protection agreements. A healthier planet awaits as we implement these discoveries for future generations.

**Scene Breakdown:**
**Scene 1: Introduction to Ecology (0s-3s)**
(Animated globe with flourishing ecosystems and diverse wildlife)
Voiceover: "Ecology advances rapidly with groundbreaking discoveries in 2025. Scientists reveal the true impact of microplastics on marine life, showing how these tiny pollutants disrupt entire food chains."

**Scene 2: Microplastic Impacts (3s-6s)**
(Researchers in labs studying microplastics with footage of ocean pollution)
Voiceover: "Nature's resilience shines as researchers document coral reefs and forests regenerating in unexpected ways. Climate change insights deepen as experts uncover new patterns in polar ice cap melting and its global effects."

**Scene 3: Ecosystem Resilience (6s-9s)**
(Visuals of coral reefs and forests regenerating with time-lapses)
Voiceover: "Biodiversity thrives in hotspots as explorers find new species in the Amazon and other rich ecosystems. Urban ecology breakthroughs transform city planning with green infrastructure that supports wildlife."

**Scene 4: Climate Insights (9s-12s)**
(Scientists examining climate change effects on polar ice caps)
Voiceover: "Human actions have consequences, but also solutions emerge through global conservation efforts. Sustainable futures are possible as renewable energy and eco-friendly technologies become mainstream."

**Scene 5: Urban Solutions (12s-15s)**
(Experts studying urban ecology and green city initiatives)
Voiceover: "Global cooperation is key as nations unite for environmental protection agreements. A healthier planet awaits as we implement these discoveries for future generations."

**Scene 6: Biodiversity Hotspots (15s-18s)**
(Explorers in the Amazon rainforest and other rich ecosystems)
Voiceover: ""

**Scene 7: Human Impact (18s-21s)**
(Images of deforestation, pollution, and conservation efforts)
Voiceover: ""

**Scene 8: Sustainable Futures (21s-24s)**
(Renewable energy sources and eco-friendly technologies)
Voiceover: ""

**Scene 9: Global Cooperation (24s-27s)**
(International summits and agreements on environmental protection)
Voiceover: ""

**Scene 10: Ecological Future (27s-30s)**
(Visuals of a thriving, balanced ecosystem with a hopeful message)
Voiceover: ""'''

    print("Testing script parsing with sample script...")
    
    # Parse the script
    parsed_script = script_parsing_service.parse_script(sample_script)
    
    print(f"Title: {parsed_script.get('title')}")
    print(f"Full narrative: {parsed_script.get('full_narrative', '')}")
    
    # Extract voiceover text
    voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
    print(f"\nExtracted voiceover text: {voiceover_text}")
    
    # Count words
    word_count = len(voiceover_text.split())
    print(f"Word count: {word_count}")
    
    # Check scenes
    scenes = parsed_script.get('scenes', [])
    print(f"\nNumber of scenes: {len(scenes)}")
    
    # Check if we have a continuous narrative
    if voiceover_text and len(voiceover_text.split()) > 50:
        print("\n✓ Successfully extracted continuous narrative")
    else:
        print("\n✗ Failed to extract continuous narrative")
        
    # Check if scenes have voiceover content
    scenes_with_voiceover = [s for s in scenes if s.get('voiceover', '').strip()]
    print(f"Scenes with voiceover content: {len(scenes_with_voiceover)}")
    
    if scenes_with_voiceover:
        print("\nVoiceover content by scene:")
        for i, scene in enumerate(scenes_with_voiceover):
            voiceover = scene.get('voiceover', '')
            print(f"  Scene {scene.get('scene_number')}: {voiceover}")
    
    print("\n\nTest completed!")

if __name__ == '__main__':
    test_script_parsing_with_sample()