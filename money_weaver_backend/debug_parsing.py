import sys
import os
import re
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

def debug_parsing():
    """Debug the parsing of the problematic script"""
    
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

    print("Debugging the parsing of the problematic script...")
    
    # Try to extract voiceover lines with regex
    voiceover_matches = re.findall(r'Voiceover:\s*["]?([^"\n]*)["]?', problematic_script, re.IGNORECASE)
    print(f"Voiceover matches found: {len(voiceover_matches)}")
    for i, match in enumerate(voiceover_matches):
        print(f"  {i+1}: '{match}'")
    
    # Try to extract all quoted text
    quoted_matches = re.findall(r'"([^"]*)"', problematic_script)
    print(f"\nQuoted text matches found: {len(quoted_matches)}")
    for i, match in enumerate(quoted_matches):
        print(f"  {i+1}: '{match}'")
    
    # Try to extract all text after "Voiceover:" patterns
    voiceover_pattern = r'Voiceover:\s*["]?([^"\n]*)["]?'
    voiceover_matches_detailed = re.finditer(voiceover_pattern, problematic_script, re.IGNORECASE)
    print(f"\nDetailed voiceover matches:")
    for match in voiceover_matches_detailed:
        print(f"  Full match: '{match.group(0)}'")
        print(f"  Captured group: '{match.group(1)}'")
        
    # Try to manually parse line by line
    print("\n\nManual line-by-line parsing:")
    lines = problematic_script.split('\n')
    for i, line in enumerate(lines):
        line = line.strip()
        if line.startswith('Voiceover:'):
            print(f"  Line {i+1}: '{line}'")
            # Extract the text after "Voiceover:"
            voiceover_text = line[10:].strip()  # Remove "Voiceover:" prefix
            # Remove quotes if present
            if voiceover_text.startswith('"') and voiceover_text.endswith('"'):
                voiceover_text = voiceover_text[1:-1]
            print(f"    Extracted: '{voiceover_text}'")

if __name__ == '__main__':
    debug_parsing()