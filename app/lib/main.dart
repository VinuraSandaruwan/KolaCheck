import 'dart:convert';
import 'dart:io';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:image_picker/image_picker.dart';
import 'advice.dart';
import 'classifier.dart';

// Set to your laptop's LAN IP (phone and laptop on same Wi-Fi) or a deployed URL.
const backendUrl = 'http://192.168.1.10:8000';
const societyId = 'demo';
const unsureBelow = 0.60;

void main() => runApp(const KolaCheckApp());

class KolaCheckApp extends StatelessWidget {
  const KolaCheckApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'KolaCheck',
        theme: ThemeData(colorSchemeSeed: const Color(0xFF2E7D32), useMaterial3: true),
        home: const Home(),
      );
}

class Home extends StatefulWidget {
  const Home({super.key});
  @override
  State<Home> createState() => _HomeState();
}

class _HomeState extends State<Home> {
  final _clf = Classifier();
  final _picker = ImagePicker();
  final _pending = <Map<String, dynamic>>[];
  bool _ready = false, _busy = false;
  String _lang = 'en', _sync = '';
  File? _photo;
  Prediction? _pred;
  String? _error;

  @override
  void initState() {
    super.initState();
    _clf.load().then((_) => setState(() => _ready = true)).catchError(
        (e) => setState(() => _error = 'Model not loaded: $e'));
  }

  String t(String k) => ui[k]![_lang]!;

  Future<void> _scan(ImageSource src) async {
    final x = await _picker.pickImage(source: src, maxWidth: 1024, imageQuality: 90);
    if (x == null) return;
    setState(() { _busy = true; _photo = File(x.path); _pred = null; _error = null; });
    try {
      final p = await _clf.predict(_photo!);
      setState(() => _pred = p);
      if (p.confidence >= unsureBelow) {
        _pending.add({'label': p.label, 'confidence': p.confidence,
                      'society_id': societyId, 'device_id': 'phone'});
      }
      _flush();
    } catch (e) {
      setState(() => _error = '$e');
    } finally {
      setState(() => _busy = false);
    }
  }

  // Offline-first: keep results queued, send when a connection exists.
  Future<void> _flush() async {
    for (final row in List.of(_pending)) {
      try {
        final r = await http.post(Uri.parse('$backendUrl/api/scans'),
            headers: {'Content-Type': 'application/json'}, body: jsonEncode(row))
            .timeout(const Duration(seconds: 5));
        if (r.statusCode == 200) _pending.remove(row);
      } catch (_) { break; }
    }
    if (mounted) setState(() => _sync = _pending.isEmpty ? 'Synced' : '${_pending.length} waiting to sync');
  }

  @override
  Widget build(BuildContext context) {
    final p = _pred;
    final sure = p != null && p.confidence >= unsureBelow;
    return Scaffold(
      appBar: AppBar(title: const Text('KolaCheck 🍃')),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        SegmentedButton<String>(
          segments: [for (final e in langs.entries) ButtonSegment(value: e.key, label: Text(e.value))],
          selected: {_lang},
          onSelectionChanged: (s) => setState(() => _lang = s.first),
        ),
        const SizedBox(height: 12),
        Text(t('hint'), textAlign: TextAlign.center),
        const SizedBox(height: 12),
        Row(children: [
          Expanded(child: FilledButton.icon(
              onPressed: _ready && !_busy ? () => _scan(ImageSource.camera) : null,
              icon: const Icon(Icons.photo_camera), label: Text(t('camera')))),
          const SizedBox(width: 8),
          Expanded(child: OutlinedButton.icon(
              onPressed: _ready && !_busy ? () => _scan(ImageSource.gallery) : null,
              icon: const Icon(Icons.photo_library), label: Text(t('gallery')))),
        ]),
        if (_photo != null) Padding(
          padding: const EdgeInsets.only(top: 12),
          child: ClipRRect(borderRadius: BorderRadius.circular(12),
              child: Image.file(_photo!, height: 240, fit: BoxFit.cover))),
        if (_busy) const Padding(padding: EdgeInsets.all(24), child: Center(child: CircularProgressIndicator())),
        if (_error != null) Padding(padding: const EdgeInsets.only(top: 12),
            child: Text(_error!, style: const TextStyle(color: Colors.red))),
        if (p != null) Card(
          margin: const EdgeInsets.only(top: 12),
          child: Padding(padding: const EdgeInsets.all(16), child: sure
            ? Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(titles[p.label] ?? p.label, style: Theme.of(context).textTheme.headlineSmall),
                const SizedBox(height: 4),
                Text('${t('conf')}: ${(p.confidence * 100).round()}%'),
                LinearProgressIndicator(value: p.confidence),
                const SizedBox(height: 12),
                Text(advice[p.label]?[_lang] ?? ''),
                if (p.label != 'healthy') ...[
                  const SizedBox(height: 8),
                  Text(askOfficer[_lang]!, style: const TextStyle(fontWeight: FontWeight.w600)),
                ],
              ])
            : Text(t('unsure'))),
        ),
        if (_sync.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 8),
            child: Text(_sync, textAlign: TextAlign.center, style: const TextStyle(color: Colors.grey))),
      ]),
    );
  }
}
