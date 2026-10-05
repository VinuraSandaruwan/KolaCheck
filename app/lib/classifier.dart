import 'dart:io';
import 'package:flutter/services.dart' show rootBundle;
import 'package:image/image.dart' as img;
import 'package:tflite_flutter/tflite_flutter.dart';

class Prediction {
  final String label;
  final double confidence;
  final List<MapEntry<String, double>> ranked;
  Prediction(this.label, this.confidence, this.ranked);
}

class Classifier {
  static const size = 224;
  late final Interpreter _interp;
  late final List<String> labels;

  Future<void> load() async {
    _interp = await Interpreter.fromAsset('assets/model.tflite');
    labels = (await rootBundle.loadString('assets/labels.txt'))
        .split('\n').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
  }

  Future<Prediction> predict(File file) async {
    var image = img.decodeImage(await file.readAsBytes())!;
    image = img.bakeOrientation(image);
    final r = img.copyResize(image, width: size, height: size);
    // Raw 0-255 floats: the model rescales internally (see train.py).
    final input = [
      List.generate(size, (y) => List.generate(size, (x) {
            final p = r.getPixel(x, y);
            return [p.r.toDouble(), p.g.toDouble(), p.b.toDouble()];
          }))
    ];
    final output = [List<double>.filled(labels.length, 0)];
    _interp.run(input, output);
    final ranked = [
      for (var i = 0; i < labels.length; i++) MapEntry(labels[i], output[0][i])
    ]..sort((a, b) => b.value.compareTo(a.value));
    return Prediction(ranked.first.key, ranked.first.value, ranked);
  }
}
