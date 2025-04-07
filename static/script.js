document.addEventListener('DOMContentLoaded', () => {
    const optionsForm = document.getElementById('quiz-options-form');
    const quizArea = document.getElementById('quiz-area');
    const resultsArea = document.getElementById('results-area');
    const errorMessageDiv = document.getElementById('error-message');
    const subtypeErrorDiv = document.getElementById('subtype-error');
    const submitButton = optionsForm.querySelector('button[type="submit"]');
    const spinner = submitButton.querySelector('.spinner-border');
    const apiKeyInput = document.getElementById('apiKey');
    const scoreDisplay = document.getElementById('score-display');
    const showAnswersBtn = document.getElementById('show-answers-btn');
    const restartQuizBtn = document.getElementById('restart-quiz-btn');
    // --- YENİ: Spesifik İstek Input'u ---
    const specificRequestInput = document.getElementById('specific_request');
    // -----------------------------------

    let currentQuizData = null;

    // --- Quiz Oluşturma ---
    optionsForm.addEventListener('submit', async (event) => {
        event.preventDefault();
        clearPreviousQuiz();

        // Seçilen Soru Alt Tiplerini Al
        const selectedSubtypes = Array.from(optionsForm.querySelectorAll('input[name="question_subtypes"]:checked'))
                                     .map(cb => cb.value);

        if (selectedSubtypes.length === 0) {
            subtypeErrorDiv.classList.remove('d-none');
            optionsForm.querySelector('.question-subtypes-grid').style.border = '1px solid red';
            return;
        } else {
            subtypeErrorDiv.classList.add('d-none');
            optionsForm.querySelector('.question-subtypes-grid').style.border = '1px solid #e9ecef'; // Stili sıfırla
        }


        submitButton.disabled = true;
        spinner.classList.remove('d-none');

        const formData = {
            apiKey: apiKeyInput.value,
            ders: document.getElementById('ders').value,
            konu: document.getElementById('konu').value,
            difficulty: document.getElementById('difficulty').value,
            num_questions: document.getElementById('num_questions').value,
            question_subtypes: selectedSubtypes,
            // --- YENİ: Spesifik isteği ekle ---
            specific_request: specificRequestInput.value.trim() // Değeri al ve boşlukları temizle
            // -----------------------------------
        };

        if (!formData.apiKey) {
            showError('Lütfen Gemini API Anahtarınızı girin.');
            finalizeSubmitButton();
            return;
        }

        try {
            const response = await fetch('/generate_quiz', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(formData),
            });

            const data = await response.json();

            if (!response.ok) {
                 if (response.status === 404 && data.error) {
                      throw new Error(data.error);
                 }
                throw new Error(data.error || `Sunucu Hatası: ${response.status}`);
            }

            if (!data.quiz || data.quiz.length === 0) {
                showError('API belirtilen kriterlere uygun soru üretemedi.');
            } else {
                currentQuizData = data.quiz;
                displayInteractiveQuiz(currentQuizData);
            }

        } catch (error) {
            console.error('Quiz oluşturma hatası:', error);
            showError(`Quiz oluşturulamadı: ${error.message}`);
        } finally {
            finalizeSubmitButton();
        }
    });

    // --- İnteraktif Quiz'i Gösterme ---
    // (Bu fonksiyonda değişiklik yok, önceki cevapla aynı)
    function displayInteractiveQuiz(quiz) {
        quizArea.innerHTML = ''; // Önceki içeriği temizle

        quiz.forEach((item, index) => {
            const card = document.createElement('div');
            card.classList.add('question-card');
            card.id = `question-${item.id}`;
            card.dataset.correctAnswer = item.correct_answer;
            card.dataset.explanation = item.explanation;
            card.dataset.questionTypeDesc = item.question_type_description;

            const header = document.createElement('div');
            header.classList.add('question-header');
            const qNumber = document.createElement('span');
            qNumber.classList.add('question-number');
            qNumber.textContent = `Soru ${index + 1}`;
            header.appendChild(qNumber);
            const qTypeBadge = document.createElement('span');
            qTypeBadge.classList.add('question-type-badge');
            qTypeBadge.textContent = item.question_type_description || 'Çoktan Seçmeli';
            header.appendChild(qTypeBadge);
            card.appendChild(header);

            const qText = document.createElement('p');
            qText.classList.add('question-text');
            qText.innerText = item.question;
            card.appendChild(qText);

            const optionsList = document.createElement('ul');
            optionsList.classList.add('options-list');
            if (item.options && Array.isArray(item.options) && item.options.length === 5) {
                const letters = ["A", "B", "C", "D", "E"];
                item.options.forEach((optionText, optionIndex) => {
                    const wrapper = document.createElement('li');
                    wrapper.classList.add('form-check');
                    const input = document.createElement('input');
                    input.classList.add('form-check-input');
                    input.type = 'radio';
                    input.name = `question_${item.id}`;
                    input.value = letters[optionIndex];
                    input.id = `q${item.id}_opt${letters[optionIndex]}`;
                    const label = document.createElement('label');
                    label.classList.add('form-check-label');
                    label.setAttribute('for', `q${item.id}_opt${letters[optionIndex]}`);
                    label.innerText = optionText.replace(/^[A-E]\)\s*/, '');
                    wrapper.appendChild(input);
                    wrapper.appendChild(label);
                    optionsList.appendChild(wrapper);
                });
            } else {
                optionsList.innerHTML = '<p class="text-danger">Hata: Bu soru için 5 seçenek bulunamadı.</p>';
            }
            card.appendChild(optionsList);

             const explanationBox = document.createElement('div');
             explanationBox.classList.add('explanation-box', 'd-none');
             card.appendChild(explanationBox);
            quizArea.appendChild(card);
        });

        const finishButton = document.createElement('button');
        finishButton.id = 'finish-quiz-btn';
        finishButton.classList.add('btn', 'btn-success', 'btn-lg', 'w-100', 'mt-4');
        finishButton.innerHTML = '<i class="bi bi-check2-all me-2"></i> Quiz\'i Bitir ve Sonuçları Gör';
        finishButton.addEventListener('click', submitQuiz);
        quizArea.appendChild(finishButton);
    }


    // --- Quiz'i Gönderme ve Değerlendirme ---
    // (Bu fonksiyonda değişiklik yok, önceki cevapla aynı)
    function submitQuiz() {
        if (!currentQuizData) return;
        let score = 0;
        const questions = quizArea.querySelectorAll('.question-card');
        const totalQuestions = questions.length;
        let allAnswered = true;

        questions.forEach(card => {
            const questionId = card.id.split('-')[1];
            const correctAnswerLetter = card.dataset.correctAnswer;
            const explanationText = card.dataset.explanation;
            let userAnswerLetter = null;
            const checkedRadio = card.querySelector('input[type="radio"]:checked');
            if (checkedRadio) {
                userAnswerLetter = checkedRadio.value;
            } else {
                allAnswered = false;
            }
            const isCorrect = userAnswerLetter === correctAnswerLetter;
            card.classList.add(isCorrect ? 'correct' : 'incorrect');
            const explanationBox = card.querySelector('.explanation-box');
            explanationBox.classList.remove('d-none');
            let explanationHTML = `<strong>Açıklama:</strong> ${explanationText}<br>`;
            const correctOptionLabel = card.querySelector(`label[for='q${questionId}_opt${correctAnswerLetter}']`);
            if (correctOptionLabel) {
                explanationHTML += `Doğru Cevap: <span class="correct-highlight">(${correctAnswerLetter}) ${correctOptionLabel.innerText}</span>`;
            } else {
                 explanationHTML += `Doğru Cevap: ${correctAnswerLetter}`;
            }
            if (!isCorrect && userAnswerLetter) {
                const userAnswerLabel = card.querySelector(`label[for='q${questionId}_opt${userAnswerLetter}']`);
                 if (userAnswerLabel) {
                      explanationHTML += `<br>Sizin Cevabınız: <span class="your-answer-highlight">(${userAnswerLetter}) ${userAnswerLabel.innerText}</span>`;
                 } else {
                      explanationHTML += `<br>Sizin Cevabınız: ${userAnswerLetter}`;
                 }
            } else if (!userAnswerLetter) {
                 explanationHTML += `<br><span class="your-answer-highlight">Bu soruyu cevaplamadınız.</span>`;
            }
            explanationBox.innerHTML = explanationHTML;
            if (isCorrect) {
                score++;
            }
            card.querySelectorAll('input[type="radio"]').forEach(input => input.disabled = true);
        });

        scoreDisplay.innerHTML = `<i class="bi bi-trophy me-2"></i> Sonuç: <strong>${score} / ${totalQuestions}</strong>`;
        resultsArea.classList.remove('d-none');
        quizArea.querySelector('#finish-quiz-btn')?.remove();
        showAnswersBtn.innerHTML = '<i class="bi bi-eye-slash-fill me-1"></i> Açıklamaları Gizle';
        showAnswersBtn.dataset.state = 'visible';
        document.querySelectorAll('.explanation-box').forEach(el => el.classList.remove('d-none'));
        resultsArea.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }


     // --- Yardımcı Fonksiyonlar ---
     // (Bu bölümde değişiklik yok, önceki cevapla aynı)
    function clearPreviousQuiz() {
        quizArea.innerHTML = '';
        resultsArea.classList.add('d-none');
        errorMessageDiv.classList.add('d-none');
        errorMessageDiv.textContent = '';
        subtypeErrorDiv.classList.add('d-none');
        optionsForm.querySelector('.question-subtypes-grid').style.border = '1px solid #e9ecef';
        currentQuizData = null;
        // Spesifik istek kutusunu da temizleyebiliriz (opsiyonel)
        // specificRequestInput.value = '';
    }
    function showError(message) {
        errorMessageDiv.textContent = message;
        errorMessageDiv.classList.remove('d-none');
        errorMessageDiv.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
    function finalizeSubmitButton() {
        submitButton.disabled = false;
        spinner.classList.add('d-none');
    }


     // --- Sonuç Alanı Butonları ---
     // (Bu bölümde değişiklik yok, önceki cevapla aynı)
     showAnswersBtn.addEventListener('click', () => {
         const explanationBoxes = document.querySelectorAll('.explanation-box');
         const currentState = showAnswersBtn.dataset.state;
         if (currentState === 'visible') {
             explanationBoxes.forEach(el => el.classList.add('d-none'));
             showAnswersBtn.innerHTML = '<i class="bi bi-eye-fill me-1"></i> Açıklamaları Göster';
             showAnswersBtn.dataset.state = 'hidden';
         } else {
             explanationBoxes.forEach(el => el.classList.remove('d-none'));
             showAnswersBtn.innerHTML = '<i class="bi bi-eye-slash-fill me-1"></i> Açıklamaları Gizle';
             showAnswersBtn.dataset.state = 'visible';
         }
     });
     restartQuizBtn.addEventListener('click', () => {
         clearPreviousQuiz();
         optionsForm.scrollIntoView({ behavior: 'smooth', block: 'start' });
         document.getElementById('ders').value = '';
         document.getElementById('konu').value = '';
         specificRequestInput.value = ''; // Spesifik istek kutusunu temizle
     });

});