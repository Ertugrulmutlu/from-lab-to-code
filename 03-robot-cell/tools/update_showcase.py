"""Opt-in, guarded patch for the existing From Lab to Code showcase.

Run from the project directory after verifying the local demo. Check expected
content before writing either file; running twice is safe.
"""
from pathlib import Path

root = Path(__file__).resolve().parents[2]
site = root / "docs" / "app.js"
readme = root / "README.md"
if not site.is_file() or not readme.is_file():
    raise SystemExit("Site files not found. Extract 03-robot-cell inside the repository root.")

old_card = "{id:'03',title:'Signal Correlation',short:'Cross-correlation · Time Delay · FFT',category:'Signal Processing',description:'Visualizing patterns and shifts in signals.',githubUrl:'',articleUrl:'',status:'planned',featured:false,icon:'wave',accent:'orange'}"
old_published_card = "{id:'03',title:'Robot Cell Playground',short:'Robot kinematics · Sensors · State machines',category:'Robotics',description:'A small 3D robotics simulation with a Python control loop: detect colored parts, compute robotic motion, and sort them into destination bins.',githubUrl:'https://github.com/Ertugrulmutlu/from-lab-to-code/tree/main/03-robot-cell',articleUrl:'',status:'published',featured:false,icon:'robot',accent:'amber'}"
new_card = "{id:'03',title:'Robot Cell Playground',short:'Kinematics · Digital I/O · Sorting FSM',category:'Robotics',description:'Simulate an automated robot cell, change live I/O wiring, inject sensor or gripper faults, and explore why sorting succeeds or fails.',githubUrl:'https://github.com/Ertugrulmutlu/from-lab-to-code/tree/main/03-robot-cell',articleUrl:'',status:'published',featured:false,icon:'robot',accent:'amber'}"
previous = "| 02 | [Spatial Audio Playground — From Theory to Binaural Sound](02-spatial-audio/) | Cross-correlation, ITD/ILD, HRIR/HRTF, binaural convolution, interactive soundstage |"
row = "| 03 | [Robot Cell Playground](03-robot-cell/) | Robot kinematics, digital I/O wiring lab, sorting FSM, Three.js |"
old_row = "| 03 | [Robot Cell Playground](03-robot-cell/) | Robot kinematics, sensors, sorting FSM, Three.js |"

site_content = site.read_text(encoding="utf-8")
readme_content = readme.read_text(encoding="utf-8")
if new_card not in site_content and old_card not in site_content and old_published_card not in site_content:
    raise SystemExit("docs/app.js differs from expected: update Project #03 manually; no changes made.")
if row not in readme_content and old_row not in readme_content and previous not in readme_content:
    raise SystemExit("README projects table differs from expected: update it manually; no changes made.")

site_new = site_content.replace(old_card, new_card, 1).replace(old_published_card, new_card, 1)
readme_new = readme_content.replace(old_row, row, 1)
if row not in readme_new:
    readme_new = readme_new.replace(previous, previous + '\n' + row, 1)
if site_new != site_content:
    site.write_text(site_new, encoding="utf-8")
    print("Updated docs/app.js Project #03")
else:
    print("Project #03 already updated")
if readme_new != readme_content:
    readme.write_text(readme_new, encoding="utf-8")
    print("Added Project #03 to root README")
else:
    print("Root README row already exists")
