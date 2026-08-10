import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.services.script_parsing_service import script_parsing_service

def test_problematic_case():
    """Test with the exact problematic output from the issue"""
    
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

    print("Testing with the exact problematic output from the issue...")
    
    # Parse the script
    parsed_script = script_parsing_service.parse_script(problematic_script)
    
    print(f"Title: {parsed_script.get('title')}")
    print(f"Full narrative: '{parsed_script.get('full_narrative', '')}'")
    
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
    
    # Extract voiceover text
    voiceover_text = script_parsing_service.extract_voiceover_text(parsed_script)
    print(f"\nExtracted voiceover text: {voiceover_text}")
    
    # Count words
    word_count = len(voiceover_text.split())
    print(f"Word count: {word_count}")
    
    # Check if we can create a more coherent narrative
    if word_count >= 30:  # At least 30 words for a 30-second video
        print("\n✓ Successfully extracted enough content for a coherent narrative")
    else:
        print("\n✗ Still not enough content for a coherent narrative")
        
    # Show scenes with voiceover content
    scenes_with_voiceover = [s for s in scenes if s.get('voiceover', '').strip()]
    print(f"\nScenes with voiceover content: {len(scenes_with_voiceover)}")
    
    if scenes_with_voiceover:
        print("\nVoiceover content by scene:")
        for i, scene in enumerate(scenes_with_voiceover):
            voiceover = scene.get('voiceover', '')
            print(f"  Scene {scene.get('scene_number')}: {voiceover}")
    
    # Try to create a more coherent narrative by connecting the clauses
    if scenes_with_voiceover:
        print("\n\nAttempting to create a more coherent narrative:")
        narrative_parts = []
        for scene in scenes_with_voiceover:
            voiceover = scene.get('voiceover', '').strip()
            if voiceover:
                # Add period if missing and not ending with punctuation
                if voiceover and not voiceover[-1] in '.!?':
                    voiceover += '.'
                narrative_parts.append(voiceover)
        
        # Join with spaces and clean up extra whitespace
        import re
        coherent_narrative = ' '.join(narrative_parts)
        coherent_narrative = re.sub(r'\s+', ' ', coherent_narrative)
        coherent_narrative = coherent_narrative.strip()
        
        print(f"Coherent narrative: {coherent_narrative}")
        print(f"Word count of coherent narrative: {len(coherent_narrative.split())}")
    
    print("\n\nTest completed!")

if __name__ == '__main__':
    test_problematic_case()