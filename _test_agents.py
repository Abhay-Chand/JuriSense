"""Test all 3 agents directly"""
import asyncio
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, 'backend')

async def test_agents():
    # Test 1: Researcher - knowledge mode
    print('===== RESEARCHER (knowledge) =====')
    from agents.researcher import agent as researcher
    r = await researcher.run('What is Section 138 of NIA?', mode='knowledge')
    print('Mode:', r.get('mode_used'))
    print('Laws:', r.get('laws_retrieved'))
    resp = r.get('response', '')
    print('Response preview:', resp[:300])
    print()

    # Test 2: Researcher - pathfinder mode
    print('===== RESEARCHER (pathfinder) =====')
    r2 = await researcher.run('How to file an FIR?', mode='pathfinder')
    print('Mode:', r2.get('mode_used'))
    print('Laws:', r2.get('laws_retrieved'))
    resp2 = r2.get('response', '')
    print('Response preview:', resp2[:300])
    print()

    # Test 3: Drafter
    print('===== DRAFTER =====')
    from agents.drafter import agent as drafter
    d = await drafter.run('Draft a cheque bounce notice for bounced cheque of 5 lakhs', mode='document')
    print('Mode:', d.get('mode_used'))
    print('Doc type:', d.get('document_type'))
    resp3 = d.get('response', '')
    print('Response preview:', resp3[:300])
    print()

    # Test 4: Reviewer - scrutiny
    print('===== REVIEWER (scrutiny) =====')
    from agents.reviewer import agent as reviewer
    v = await reviewer.run('I had a motor accident 2 years ago and want to file a claim now', mode='scrutiny')
    print('Mode:', v.get('mode_used'))
    resp4 = v.get('response', '')
    print('Response preview:', resp4[:300])

asyncio.run(test_agents())
