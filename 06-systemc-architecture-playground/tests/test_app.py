import unittest
from app import parse_output, parse_vcd, inputs, auto_schematic, ROOT, model_files, schematic_source, checked_files

class TestApp(unittest.TestCase):
    def test_events(self):
        r = parse_output('hello\n@@EVENT@@{"kind":"signal","delta":2,"time_ns":5}\n@@VCD_BEGIN@@\n$timescale 1 ns $end\n$enddefinitions $end\n#5\n@@VCD_END@@', 0)
        self.assertTrue(r['ok'])
        self.assertEqual(r['events'][0]['delta'], 2)
        self.assertEqual(r['waveform']['end'], 5)

    def test_vcd(self):
        v = parse_vcd('$timescale\n 1 ns\n$end\n$scope module SystemC $end\n$var wire 1 ! A $end\n$var wire 4 # DATA $end\n$upscope $end\n$enddefinitions $end\n#0\n0!\nb0000 #\n#10\n1!\nb1010 #')
        self.assertEqual(v['timescale'], '1 ns')
        self.assertEqual(v['signals'][0]['changes'], [[0,'0'], [10,'1']])
        self.assertEqual(v['signals'][1]['changes'][-1], [10,'1010'])

    def test_input(self):
        self.assertEqual(inputs({'model':'ripple','code':'test','width':32,'a':4294967295,'b':0})[2][0], '4294967295')
        with self.assertRaises(ValueError):
            inputs({'model':'full','code':'test','a':2,'b':0})
        with self.assertRaises(ValueError):
            inputs({'model':'ripple','code':'test','width':3})

    def test_schematic(self):
        code = schematic_source('full', model_files('full'))
        s = auto_schematic(code)
        self.assertTrue(any(i['name'] == 'dut' and i['type'] == 'FullAdder' for i in s['instances']))
        self.assertIn('a', s['signals'])
        self.assertTrue(any(b.get('instance') == 'dut' and b.get('port') == 'a' for b in s['bindings'] if b['kind'] == 'signal'))

    def test_all_schematics(self):
        for model in ('functional', 'full', 'ripple', 'cpu'):
            with self.subTest(model=model):
                s = auto_schematic(schematic_source(model, model_files(model)))
                self.assertEqual(len(s['instances']), 2)
                self.assertTrue(s['bindings'])
        ripple = auto_schematic(schematic_source('ripple', model_files('ripple')))
        self.assertTrue(any(i['type'] == 'RippleObserver' for i in ripple['instances']))
        cpu = auto_schematic(schematic_source('cpu', model_files('cpu')))
        self.assertTrue(any(b['kind'] == 'bind' for b in cpu['bindings']))

    def test_directed_processes_and_vectors(self):
        full = auto_schematic(schematic_source('full', model_files('full')))
        stages = full['modules']['FullAdder']['processes']
        self.assertEqual([p['name'] for p in stages], ['stage1','stage2','stage3'])
        self.assertEqual(stages[0]['writes'][0]['expression'], 'a.read() ^ b.read()')
        self.assertEqual(next(b['direction'] for b in full['bindings'] if b.get('instance')=='dut' and b.get('port')=='sum'), 'out')
        ripple = auto_schematic(schematic_source('ripple', model_files('ripple')))
        self.assertNotIn('n[]', ripple['signals'])
        child = ripple['modules']['Ripple']['children'][0]
        self.assertEqual(dict((b['port'],b['net']) for b in child['bindings'])['cout'], 'carry[i+1]')
        cpu = auto_schematic(schematic_source('cpu', model_files('cpu')))
        self.assertEqual(cpu['modules']['CPU']['processes'][0]['kind'], 'SC_THREAD')
        self.assertEqual(cpu['modules']['Memory']['callbacks'], ['transport'])

    def test_multifile(self):
        for model in ('functional','full','ripple','cpu'):
            files = model_files(model)
            self.assertIn('main.cpp', files)
            self.assertTrue(any(n.endswith('.h') for n in files))
            inputs({'model':model,'files':files,'a':1,'b':1})
            with self.assertRaises(ValueError):
                checked_files(model, {**files, '../bad.cpp':'bad'})

if __name__ == '__main__':
    unittest.main()
