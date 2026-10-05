// Plain-language text. Sinhala/Tamil MUST be reviewed by a native speaker
// (ideally a grower or extension officer) before real use.
const langs = {'en': 'English', 'si': 'සිංහල', 'ta': 'தமிழ்'};

const titles = {
  'algal_leaf_spot': 'Algal leaf spot', 'black_blight': 'Black blight',
  'blister_blight': 'Blister blight', 'gray_blight': 'Gray blight',
  'spider_mite': 'Spider mite damage', 'healthy': 'Healthy leaf',
};

const advice = <String, Map<String, String>>{
  'algal_leaf_spot': {
    'en': 'Orange-brown velvety spots, common on weak, shaded or poorly drained bushes.',
    'si': 'තැඹිලි-දුඹුරු පැහැති ලප; දුර්වල, සෙවණ හෝ ජලය රැඳෙන පඳුරුවල සුලභයි.',
    'ta': 'ஆரஞ்சு-பழுப்பு நிறப் புள்ளிகள்; பலவீனமான, நிழலான அல்லது வடிகால் குறைந்த செடிகளில் அதிகம்.'},
  'black_blight': {
    'en': 'Dark patches that spread and dry the leaf; can spread fast in wet weather.',
    'si': 'කළු පැහැති ලප පැතිරී කොළය වියළේ; තෙත් කාලගුණයේ ඉක්මනින් පැතිරේ.',
    'ta': 'கருமையான திட்டுகள் பரவி இலை உலரும்; ஈரமான வானிலையில் வேகமாகப் பரவும்.'},
  'blister_blight': {
    'en': 'Small translucent spots that become blisters; spreads fast in cool, misty, wet weather.',
    'si': 'කුඩා විනිවිද පෙනෙන ලප බිබිලි බවට පත්වේ; සීතල, මීදුම්, තෙත් කාලගුණයේ ඉක්මනින් පැතිරේ.',
    'ta': 'சிறிய ஒளி ஊடுருவும் புள்ளிகள் கொப்புளங்களாக மாறும்; குளிர், மூடுபனி, ஈரமான வானிலையில் வேகமாகப் பரவும்.'},
  'gray_blight': {
    'en': 'Grey-brown rings on leaves, often after damage or stress.',
    'si': 'කොළ මත අළු-දුඹුරු වළලු; බොහෝවිට හානි හෝ ආතතියෙන් පසුව.',
    'ta': 'இலைகளில் சாம்பல்-பழுப்பு வளையங்கள்; பெரும்பாலும் சேதம் அல்லது அழுத்தத்துக்குப் பின்.'},
  'spider_mite': {
    'en': 'Dull, bronzed or speckled leaves, worse in dry, hot spells.',
    'si': 'කොළ දිලිසීම නැති, දුඹුරු හෝ ලප වැටී ඇත; වියළි, උණුසුම් කාලයේ වැඩියි.',
    'ta': 'இலைகள் பளபளப்பிழந்து பழுப்பாக அல்லது புள்ளிகளுடன் காணப்படும்; வறண்ட, வெப்பமான காலத்தில் அதிகம்.'},
  'healthy': {
    'en': 'No disease signs seen. Keep checking regularly.',
    'si': 'රෝග ලක්ෂණ නොපෙනේ. නිතර පරීක්ෂා කරන්න.',
    'ta': 'நோய் அறிகுறி இல்லை. தொடர்ந்து கவனியுங்கள்.'},
};

const askOfficer = {
  'en': 'Before spraying anything, ask your extension officer or an agrochemical advisor.',
  'si': 'ඉසීමට පෙර ව්‍යාප්ති නිලධාරියෙකුගෙන් හෝ කෘෂි උපදේශකයෙකුගෙන් විමසන්න.',
  'ta': 'தெளிப்பதற்கு முன் விரிவாக்க அதிகாரி அல்லது வேளாண் ஆலோசகரிடம் கேளுங்கள்.',
};

const ui = <String, Map<String, String>>{
  'camera': {'en': 'Take photo', 'si': 'ඡායාරූපයක් ගන්න', 'ta': 'புகைப்படம் எடுக்க'},
  'gallery': {'en': 'Choose photo', 'si': 'ඡායාරූපයක් තෝරන්න', 'ta': 'படத்தைத் தேர்வு'},
  'unsure': {
    'en': 'Not sure. Retake in daylight, one leaf, close up, or ask an officer.',
    'si': 'විශ්වාස නැත. දහවල් ආලෝකයේ, එක කොළයක්, ළඟින් නැවත ගන්න, නැතහොත් නිලධාරියෙකුගෙන් අසන්න.',
    'ta': 'உறுதியில்லை. பகல் வெளிச்சத்தில் ஒரு இலையை அருகில் மீண்டும் எடுக்கவும், அல்லது அதிகாரியிடம் கேளுங்கள்.'},
  'hint': {'en': 'Photograph one leaf in daylight', 'si': 'දහවල් එක කොළයක් ඡායාරූපයට ගන්න',
           'ta': 'பகலில் ஒரு இலையைப் படமெடுக்கவும்'},
  'conf': {'en': 'Confidence', 'si': 'විශ්වාසය', 'ta': 'நம்பிக்கை'},
};
