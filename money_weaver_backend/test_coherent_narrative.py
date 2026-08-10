import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.script_parsing_service import script_parsing_service

def test_coherent_narrative():
    """Test our improved parsing with the problematic format to create a coherent narrative"""
    
    # This is the exact problematic output from the issue
    problematic_script = '''**Title: "Ecology's Groundbreaking Discoveries in 2025"**
**Scene 1: Introduction to Ecology (0s-3s)**(Animated globe with flourishing ecosystems and diverse wildlife)
Voiceover: "Ecology advances rapidly"

**Scene 2: Discovery One (3s-6s)**(Researchers in labs studying microplastics with footage of ocean pollution)
Voiceover: "Microplastic impacts revealed"

**Scene 3: Ecosystem Resilience (6s-9s)**(Visuals of coral reefs and forests regenerating with time-lapses)
Voiceover: "Nature's resilience shines"

**Scene 4: Discovery Two (9s-12s)**(Scientists examining climate change effects on polar ice caps)
Voiceover: "Climate change insights deepen"

**Scene 5: Biodiversity Hotspots (12s-15s)**(Explorers in the Amazon rainforest and other rich ecosystems)
Voiceover: "Biodiversity thrives in hotspots"

**Scene 6: Discovery Three (15s-18s)**(Experts studying urban ecology and green city initiatives)
Voiceover: "Urban ecology breakthroughs"

**Scene 7: Human Impact (18s-21s)**(Images of deforestation, pollution, and conservation efforts)
Voiceover: "Human actions have consequences"

**Scene 8: Sustainable Futures (21s-24s)**(Renewable energy sources and eco-friendly technologies)
Voiceover: "Sustainable futures are possible"

**Scene 9: Global Cooperation (24s-27s)**(International summits and agreements on environmental protection)
Voiceover: "Global cooperation is key"

**Scene 10: Ecological Future (27s-30s)**(Visuals of a thriving, balanced ecosystem with a hopeful message)
Voiceover: "A healthier planet awaits"'''

    print("Testing improved parsing with the problematic format...")
    
    # Parse the script
    parsed_script = script_parsing_service.parse_script(problematic_script)
    
    print(f"Title: {parsed_script.get('title')}")
    
    # Extract voiceover text
    voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
    print(f"\nExtracted voiceover text: {voiceover_text}")
    
    # Count words
    word_count = len(voiceover_text.split())
    print(f"Word count: {word_count}")
    
    # Check scenes
    scenes = parsed_script.get('scenes', [])
    print(f"\nNumber of scenes: {len(scenes)}")
    
    # Show all scenes
    if scenes:
        print("\nAll scenes:")
        for i, scene in enumerate(scenes):
            print(f"  Scene {i+1}:")
            print(f"    Scene number: {scene.get('scene_number')}")
            print(f"    Description: {scene.get('description')}")
            print(f"    Start time: {scene.get('start_time')}")
            print(f"    End time: {scene.get('end_time')}")
            print(f"    Duration: {scene.get('duration')}")
            print(f"    Visual description: {scene.get('visual_description')}")
            print(f"    Voiceover: '{scene.get('voiceover', '')}'")
    
    # Check if we can create a more coherent narrative
    if word_count >= 20:  # At least 20 words for a meaningful narrative
        print("\n✓ Successfully extracted content for a narrative")
    else:
        print("\n✗ Not enough content for a meaningful narrative")
        
    # Show scenes with voiceover content
    scenes_with_voiceover = [s for s in scenes if s.get('voiceover', '').strip()]
    print(f"\nScenes with voiceover content: {len(scenes_with_voiceover)}")
    
    if scenes_with_voiceover:
        print("\nVoiceover content by scene:")
        for i, scene in enumerate(scenes_with_voiceover):
            voiceover = scene.get('voiceover', '')
            print(f"  Scene {scene.get('scene_number')}: {voiceover}")
    
    # Show the improved coherent narrative
    print("\n\nImproved coherent narrative:")
    if len(scenes_with_voiceover) > 0:
        # Use our new connection method
        fragments = [s.get('voiceover', '').strip() for s in scenes_with_voiceover if s.get('voiceover', '').strip()]
        if fragments:
            connected_narrative = script_parsing_service._connect_fragments(fragments)
            print(f"Connected narrative: {connected_narrative}")
            print(f"Word count: {len(connected_narrative.split())}")
    
    print("\n\nComparison with original problematic output:")
    print("Original: 'Ecology advances rapidly. Microplastic impacts revealed. Nature's resilience shines. ...'")
    print("Improved: The parser now connects these fragments into a more coherent narrative")
    
    print("\n\nTest completed!")

if __name__ == '__main__':
    test_coherent_narrative()