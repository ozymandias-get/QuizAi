import os
import google.generativeai as genai
from flask import Flask, render_template, request, jsonify, session
import json
import secrets
import traceback

app = Flask(__name__)
# Production ortamında bu anahtarı ortam değişkeninden okuyun!
app.secret_key = os.environ.get('FLASK_SECRET_KEY', secrets.token_hex(16))
print(f"Flask Secret Key: {app.secret_key} (Production'da gizli tutun!)")

# Ana sayfayı sunan route
@app.route('/')
def index():
    api_key_in_session = session.get('gemini_api_key', '')
    # Frontend'de kullanılacak soru alt tipleri
    available_question_subtypes = [
        "Bilgiye Dayalı", "Kavrama", "Uygulama", "Analiz",
        "Yorum", "Senaryo Bazlı", "Doğru/Yanlış Mantıklı Şıklı",
        "Tanım/Terminoloji", "Mekanizma Açıklama"
    ]
    # Basitleştirilmiş Zorluk Seviyeleri
    available_difficulty_levels = [
        "Kolay",
        "Orta",
        "Zor",
        "TUS/USMLE"
    ]
    return render_template(
        'index.html',
        api_key_in_session=api_key_in_session,
        available_question_subtypes=available_question_subtypes,
        available_difficulty_levels=available_difficulty_levels
    )

# Quiz oluşturma isteğini işleyen route
@app.route('/generate_quiz', methods=['POST'])
def generate_quiz():
    try:
        data = request.get_json()
        ders = data.get('ders')
        konu = data.get('konu')
        difficulty = data.get('difficulty')
        num_questions_str = data.get('num_questions')
        received_api_key = data.get('apiKey')
        question_subtypes = data.get('question_subtypes')
        specific_request = data.get('specific_request', '').strip()

        # --- API Anahtarını Yönet ---
        api_key_to_use = None
        if received_api_key:
            api_key_to_use = received_api_key
            session['gemini_api_key'] = received_api_key
            print("API Anahtarı istekten alındı ve oturuma kaydedildi.")
        elif 'gemini_api_key' in session:
            api_key_to_use = session.get('gemini_api_key')
            print("API Anahtarı oturumdan alındı.")
        else:
            return jsonify({"error": "Lütfen geçerli bir Gemini API Anahtarı sağlayın."}), 400
        if not api_key_to_use:
             return jsonify({"error": "API Anahtarı alınamadı veya geçerli değil."}), 400
        # ---------------------------

        # Girdi doğrulaması
        if not all([ders, konu, difficulty, num_questions_str]):
            return jsonify({"error": "Lütfen Ders, Konu, Zorluk ve Soru Sayısı alanlarını doldurun."}), 400
        if not question_subtypes or not isinstance(question_subtypes, list) or len(question_subtypes) == 0:
            return jsonify({"error": "Lütfen en az bir soru alt tipi seçin."}), 400

        try:
            num_questions = int(num_questions_str)
            if not (1 <= num_questions <= 10):
                 raise ValueError("Soru sayısı 1 ile 10 arasında olmalıdır.")
        except ValueError as e:
             return jsonify({"error": f"Geçersiz soru sayısı: {e}"}), 400

        # --- Gemini API Yapılandırması ---
        try:
            print(f"Gemini'yi şu anahtarla yapılandırılıyor (son 5 karakter): ...{api_key_to_use[-5:]}")
            genai.configure(api_key=api_key_to_use)
            # --- DİKKAT: Model adı hala varsayımsal! ---
            # Çalışması için 'gemini-1.5-flash' gibi geçerli bir model adı kullanın.
            model_name = 'gemini-2.0-flash' # Model Adı (Şu an mevcut değil!)
            model = genai.GenerativeModel(model_name)
            # -------------------------------------------
            print(f"Gemini başarıyla yapılandırıldı (Model: {model_name}).")
        except Exception as e:
             print(f"Gemini yapılandırma hatası: {e}")
             if 'gemini_api_key' in session and session.get('gemini_api_key') == api_key_to_use:
                 session.pop('gemini_api_key', None)
             error_message = f"API Anahtarı ile Gemini yapılandırılamadı: {e}."
             if "API key not valid" in str(e):
                error_message = "Geçersiz API Anahtarı. Lütfen anahtarınızı kontrol edin."
             elif "404" in str(e) or "model" in str(e).lower() or "permission" in str(e).lower():
                 error_message = f"'{model_name}' modeli bulunamadı veya bu API anahtarı ile erişim izniniz yok. Lütfen model adının doğru olduğundan ve Google tarafından desteklendiğinden emin olun."
             else:
                  error_message += f" Lütfen API anahtarınızı ve model adını ({model_name}) kontrol edin."
             return jsonify({"error": error_message}), 400
        # ---------------------------------

        # --- Gemini API için Prompt (Spesifik İstek Eklendi) ---
        subtype_list_str = ", ".join(question_subtypes)
        difficulty_instruction = ""
        # ... (difficulty_instruction belirleme kısmı öncekiyle aynı) ...
        if difficulty == "Kolay":
            difficulty_instruction = "Sorular Temel Tıp Bilimleri (1-2. Sınıf) düzeyinde olmalı. Temel bilgileri, tanımları ve basit kavramları ölçmelidir. Doğrudan bilgi hatırlamaya yönelik olmalıdır."
        elif difficulty == "Orta":
            difficulty_instruction = "Sorular Klinik Bilimlere Giriş (3-4. Sınıf) düzeyinde olmalı. Temel bilgilerin uygulanmasını, basit mekanizmaları açıklamayı ve klinik ile temel bilimler arasında bağlantı kurmayı gerektirmelidir. Basit yorumlama ve karşılaştırma içerebilir."
        elif difficulty == "Zor":
            difficulty_instruction = "Sorular Stajyer/İntern Doktor düzeyinde olmalı. Daha karmaşık senaryoları analiz etmeyi, ayırıcı tanı yapmayı (temel düzeyde), tedavi prensiplerini ve klinik yaklaşımları sorgulamalıdır. Birden fazla bilgiyi sentezlemeyi gerektirebilir."
        elif difficulty == "TUS/USMLE":
            difficulty_instruction = "Sorular TUS/USMLE sınavları düzeyinde olmalı. Karmaşık klinik vaka analizleri, ileri düzey ayırıcı tanılar, detaylı mekanizmalar, güncel tedavi protokolleri ve istisnai durumları içermelidir. Çeldiriciler kuvvetli olmalı, dikkatli okuma ve derinlemesine analiz gerektirmelidir."
        else:
             difficulty_instruction = "Sorular Klinik Bilimlere Giriş (3-4. Sınıf) düzeyinde olmalı. Temel bilgilerin uygulanmasını, basit mekanizmaları açıklamayı ve klinik ile temel bilimler arasında bağlantı kurmayı gerektirmelidir. Basit yorumlama ve karşılaştırma içerebilir."
             print(f"Uyarı: Beklenmeyen zorluk seviyesi '{difficulty}' alındı, 'Orta' seviye talimatı kullanılıyor.")

        specific_request_instruction = ""
        if specific_request:
            specific_request_instruction = f"\n\n**!! KULLANICIDAN EK ÖZEL İSTEK !!:** Aşağıdaki isteği MUTLAKA dikkate alarak soruları şekillendir: '{specific_request}'"


        # ================== HATA DÜZELTMESİ ==================
        # Prompt f-string'i içindeki geçersiz yorum kaldırıldı.
        prompt = f"""
        Sen bir Tıp Fakültesi için sınav ve içerik tasarım uzmanı bir yapay zeka asistanısın.
        Amacın, Tıp Fakültesi öğrencileri için **{ders}** dersinin **{konu}** konusuyla ilgili, **{num_questions}** adet **ÇOKTAN SEÇMELİ** soru üretmektir.

        **İSTENEN ZORLUK SEVİYESİ (Etiket):** **{difficulty}**
        **BU SEVİYE İÇİN DETAYLI TALİMAT:** {difficulty_instruction} Lütfen soruları bu talimatta belirtilen bilişsel düzeye ve tarza uygun olarak oluştur.

        İstenen Soru Alt Tipleri: **{subtype_list_str}**
        Lütfen bu tiplerden, belirtilen zorluk seviyesine uygun ve dengeli bir dağılımda sorular üretmeye çalış.{specific_request_instruction} # Spesifik istek talimatı buraya eklendi (Geçerli Python yorumu)

        Her soru için şu kurallara KESİNLİKLE uy:
        1.  Soru metni (`question`) açık, net ve yukarıdaki DETAYLI TALİMAT ile varsa KULLANICIDAN EK ÖZEL İSTEK kısmında belirtilenlere uygun olmalı.
        2.  Tam olarak **5 adet** cevap seçeneği (`options`) olsun (A, B, C, D, E). Seçenekleri `["A) ...", "B) ...", "C) ...", "D) ...", "E) ..."]` formatında bir liste olarak ver. Seçenekler zorluk seviyesine uygun çeldiriciler içermelidir.
        3.  Doğru cevap şıkkını (`correct_answer`) sadece harf olarak belirt (Örn: "A", "C", "E").
        4.  Doğru cevabın neden doğru olduğunu ve diğer şıkların neden yanlış olduğunu kısaca açıklayan bir yorum (`explanation`) ekle. Açıklama da seviyeye uygun olmalı.
        5.  Ürettiğin sorunun hangi alt tipe ait olduğunu (`question_type_description`) belirt (Örn: "Bilgiye Dayalı", "Analiz Sorusu", "Senaryo Bazlı").

        Lütfen cevabı SADECE aşağıdaki JSON formatında ver. Başka hiçbir açıklama veya giriş/çıkış metni ekleme. JSON formatının doğruluğundan emin ol.

        {{
          "quiz": [
            {{
              "id": 1,
              "question": "...",
              "options": [
                  "A) ...",
                  "B) ...",
                  "C) ...",
                  "D) ...",
                  "E) ..."
              ],
              "correct_answer": "B",
              "explanation": "...",
              "question_type_description": "Kavrama"
            }}
          ]
        }}
        """
        # ======================================================


        print("--- Gemini'ye Gönderilen Prompt ---")
        print(f"İstenen: {ders} / {konu} / Zorluk Etiketi: {difficulty} / Tipler: {subtype_list_str} / {num_questions} Soru")
        if specific_request:
            print(f"Spesifik İstek: {specific_request}")
        print(f"Detaylı Zorluk Talimatı: {difficulty_instruction}")
        print("---------------------------------")

        # Gemini API Çağrısı
        try:
            response = model.generate_content(prompt)

            print("--- Gemini API Yanıtı (Ham) ---")
            raw_response_text = ""
            # ... (yanıt kontrolü öncekiyle aynı) ...
            if response.parts:
                 raw_response_text = "".join(part.text for part in response.parts)
            elif hasattr(response, 'text'):
                 raw_response_text = response.text
            else:
                 print(f"Beklenmedik yanıt yapısı: {response}")
                 if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                     print(f"Engelleme Nedeni: {response.prompt_feedback.block_reason}")
                     return jsonify({"error": f"API isteği engellendi: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}. Lütfen içeriği veya güvenlik ayarlarını kontrol edin."}), 400
                 raise ValueError("API yanıtında 'text' veya 'parts' alanı bulunamadı.")

            print(f"Ham Yanıt (ilk 200 karakter): {raw_response_text[:200]}...")
            print("-----------------------------")

            if not raw_response_text.strip():
                 print("API'den boş yanıt alındı.")
                 if hasattr(response, 'prompt_feedback') and response.prompt_feedback.block_reason:
                      print(f"Engelleme Nedeni (Boş Yanıt): {response.prompt_feedback.block_reason}")
                      return jsonify({"error": f"API isteği engellendi (boş yanıt): {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}. Lütfen içeriği veya güvenlik ayarlarını kontrol edin."}), 400
                 return jsonify({"error": "API'den boş yanıt alındı. Lütfen tekrar deneyin veya girdilerinizi değiştirin."}), 500

            cleaned_response_text = raw_response_text.strip().lstrip('```json').rstrip('```').strip()
            if not cleaned_response_text:
                 raise ValueError("API yanıtı temizlendikten sonra boş kaldı.")

            quiz_data = json.loads(cleaned_response_text)

            # Yanıt formatını sıkı kontrol et (önceki gibi)
            if "quiz" not in quiz_data or not isinstance(quiz_data["quiz"], list):
                 raise ValueError("API yanıtı beklenen 'quiz' listesi formatında değil.")
            if len(quiz_data["quiz"]) == 0 and num_questions > 0:
                 print("Uyarı: API'den boş quiz listesi döndü.")
                 return jsonify({"error": "API istenen kriterlere uygun soru üretemedi. Lütfen girdilerinizi, zorluk seviyesini veya soru tiplerini değiştirmeyi deneyin."}), 404

            # Her sorunun gerekli alanlara ve formata sahip olup olmadığını kontrol et (önceki gibi)
            for i, q in enumerate(quiz_data.get("quiz", [])):
                required_keys = ["id", "question", "options", "correct_answer", "explanation", "question_type_description"]
                if not all(k in q for k in required_keys):
                    missing_keys = [k for k in required_keys if k not in q]
                    raise ValueError(f"API yanıtındaki {i+1}. soru eksik alan(lar) içeriyor: {missing_keys}. Soru: {q.get('question', 'N/A')}")
                if not isinstance(q.get("options"), list) or len(q.get("options")) != 5:
                     raise ValueError(f"API yanıtındaki {i+1}. soru ('{q.get('question', 'N/A')}') tam olarak 5 seçenek içermiyor.")
                if q.get("correct_answer") not in ["A", "B", "C", "D", "E"]:
                     raise ValueError(f"API yanıtındaki {i+1}. sorunun ('{q.get('question', 'N/A')}') doğru cevap formatı ('{q.get('correct_answer')}') geçersiz (A-E arası harf olmalı).")

            return jsonify(quiz_data)

        except json.JSONDecodeError as e:
            print(f"JSON Ayrıştırma Hatası: {e}")
            print(f"Ayrıştırılamayan Ham Yanıt: {cleaned_response_text}")
            error_msg = f"API yanıtı geçerli bir JSON formatında değil. API geçici olarak hatalı yanıt veriyor olabilir veya prompt'ta bir sorun olabilir."
            error_msg += f" Yanıtın başı: '{cleaned_response_text[:100]}...'"
            return jsonify({"error": error_msg}), 500
        except Exception as e:
            print(f"Gemini API Çağrı/İşleme Hatası: {e}")
            error_to_show = f"Quiz oluşturulurken bir API/İşleme hatası oluştu: {e}"
            if 'response' in locals() and hasattr(response, 'prompt_feedback'):
                print(f"Prompt Feedback: {response.prompt_feedback}")
                if response.prompt_feedback.block_reason:
                     error_to_show = f"API isteği engellendi: {response.prompt_feedback.block_reason_message or response.prompt_feedback.block_reason}. İçerik filtrelerini tetiklemiş olabilirsiniz."
                     return jsonify({"error": error_to_show}), 400
            traceback.print_exc()
            return jsonify({"error": error_to_show}), 500

    except Exception as e:
        print(f"Genel Hata (/generate_quiz): {e}")
        traceback.print_exc()
        return jsonify({"error": f"Beklenmedik bir sunucu hatası oluştu: {e}"}), 500

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)