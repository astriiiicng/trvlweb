<!DOCTYPE html>
<html lang="id">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>TripMate - AI Travel Planner</title>

    <link rel="stylesheet" href="{{ asset('css/style.css') }}">

    <style>
        .planner-card {
            width: 450px;
        }

        .preference-options {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            margin-top: 10px;
        }

        .preference-item {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 13px;
            border: 1px solid #e1e5eb;
            border-radius: 12px;
            cursor: pointer;
            background: #fff;
            transition: .2s;
        }

        .preference-item:hover {
            border-color: #172033;
            background: #f8fafc;
        }

        .preference-item input {
            width: 17px;
            height: 17px;
            cursor: pointer;
            flex-shrink: 0;
        }

        .preference-item span {
            font-size: 14px;
            cursor: pointer;
        }

        .plan-button {
            width: 100%;
            margin-top: 20px;
            padding: 15px;
            border: none;
            border-radius: 12px;
            background: #172033;
            color: white;
            font-size: 15px;
            font-weight: 700;
            cursor: pointer;
        }

        .plan-button:hover {
            background: #27344d;
        }

        .error-message {
            margin-bottom: 15px;
            padding: 12px 14px;
            background: #fff1f2;
            border: 1px solid #fecdd3;
            color: #be123c;
            border-radius: 10px;
            font-size: 13px;
        }

        .success-message {
            margin-bottom: 15px;
            padding: 12px 14px;
            background: #f0fdf4;
            border: 1px solid #bbf7d0;
            color: #166534;
            border-radius: 10px;
            font-size: 13px;
        }

        @media (max-width: 600px) {
            .preference-options {
                grid-template-columns: 1fr;
            }

            .planner-card {
                width: 100%;
            }
        }
    </style>
</head>


<body>

<header class="navbar">

    <div class="logo">
        ✈️ TripMate
    </div>

    <nav>
        <a href="{{ url('/') }}">Home</a>
        <a href="{{ route('travel.history') }}">My Trips</a>
    </nav>

</header>


<main class="hero">

    <div class="hero-content">

        <div class="badge">
            ✨ AI Travel Planner
        </div>

        <h1>
            Rencanakan perjalananmu
            <span>lebih mudah.</span>
        </h1>

        <p>
            Masukkan destinasi, tanggal perjalanan, budget,
            dan kategori wisata yang kamu sukai.
            TripMate akan membantu menyusun rekomendasi
            perjalanan secara otomatis.
        </p>

    </div>


    <div class="planner-card">

        <h2>
            Buat Rencana Perjalanan
        </h2>


        {{-- ERROR VALIDASI --}}

        @if ($errors->any())

            <div class="error-message">

                @foreach ($errors->all() as $error)

                    <div>
                        {{ $error }}
                    </div>

                @endforeach

            </div>

        @endif


        {{-- ERROR DARI CONTROLLER --}}

        @if (session('error'))

            <div class="error-message">
                {{ session('error') }}
            </div>

        @endif


        {{-- CLIENT-SIDE ERROR BOX --}}
        <div id="client-error-box" class="error-message" style="display: none;"></div>

        {{-- FORM --}}

        <form
            id="planner-form"
            action="{{ url('/travel/plan') }}"
            method="POST"
        >

            @csrf


            {{-- DESTINASI --}}

            <div class="form-group" style="margin-bottom: 15px;">

                <label for="province">
                    📍 Provinsi
                </label>

                <select
                    id="province"
                    class="form-control"
                    style="width: 100%; padding: 14px; border: 1px solid #e1e5eb; border-radius: 12px; font-size: 14px; margin-bottom: 15px;"
                    required
                >
                    <option value="">-- Pilih Provinsi --</option>
                </select>

                <label for="destination">
                    📍 Kabupaten/Kota (Destinasi)
                </label>

                <select
                    id="destination"
                    name="destination"
                    class="form-control"
                    style="width: 100%; padding: 14px; border: 1px solid #e1e5eb; border-radius: 12px; font-size: 14px;"
                    required
                    disabled
                >
                    <option value="">-- Pilih Kabupaten/Kota --</option>
                </select>

            </div>


            {{-- TANGGAL --}}

            <div class="form-row">

                <div class="form-group">

                    <label for="start_date">
                        📅 Mulai
                    </label>

                    <input
                        type="date"
                        id="start_date"
                        name="start_date"
                        value="{{ old('start_date') }}"
                        required
                    >

                </div>


                <div class="form-group">

                    <label for="end_date">
                        📅 Selesai
                    </label>

                    <input
                        type="date"
                        id="end_date"
                        name="end_date"
                        value="{{ old('end_date') }}"
                        required
                    >

                </div>

            </div>


            {{-- JUMLAH ORANG & BUDGET --}}

            <div class="form-row">

                <div class="form-group">

                    <label for="jumlah_orang">
                        👥 Jumlah Orang
                    </label>

                    <input
                        type="number"
                        id="jumlah_orang"
                        name="jumlah_orang"
                        value="{{ old('jumlah_orang', 1) }}"
                        min="1"
                        placeholder="1"
                        required
                    >

                </div>

                <div class="form-group">

                    <label for="budget">
                        💰 Total Budget (Semua)
                    </label>

                    <input
                        type="number"
                        id="budget"
                        name="budget"
                        value="{{ old('budget') }}"
                        min="0"
                        placeholder="Contoh: 1500000"
                        required
                    >

                </div>

            </div>


            {{-- KATEGORI --}}

            <div class="form-group">

                <label>
                    🎯 Kategori Wisata
                </label>

                <div class="preference-options">


                    <label class="preference-item">

                        <input
                            type="checkbox"
                            name="preferences[]"
                            value="pantai"
                            {{ in_array('pantai', old('preferences', [])) ? 'checked' : '' }}
                        >

                        <span>
                            🏖️ Pantai
                        </span>

                    </label>


                    <label class="preference-item">

                        <input
                            type="checkbox"
                            name="preferences[]"
                            value="kuliner"
                            {{ in_array('kuliner', old('preferences', [])) ? 'checked' : '' }}
                        >

                        <span>
                            🍜 Kuliner
                        </span>

                    </label>


                    <label class="preference-item">

                        <input
                            type="checkbox"
                            name="preferences[]"
                            value="alam"
                            {{ in_array('alam', old('preferences', [])) ? 'checked' : '' }}
                        >

                        <span>
                            🌿 Alam
                        </span>

                    </label>


                    <label class="preference-item">

                        <input
                            type="checkbox"
                            name="preferences[]"
                            value="budaya"
                            {{ in_array('budaya', old('preferences', [])) ? 'checked' : '' }}
                        >

                        <span>
                            🏛️ Budaya
                        </span>

                    </label>


                    <label class="preference-item">

                        <input
                            type="checkbox"
                            name="preferences[]"
                            value="hiburan"
                            {{ in_array('hiburan', old('preferences', [])) ? 'checked' : '' }}
                        >

                        <span>
                            🎡 Hiburan
                        </span>

                    </label>


                </div>

            </div>


            {{-- KETERANGAN TAMBAHAN --}}

            <div class="form-group" style="margin-top: 20px;">

                <label for="context">
                    📝 Keterangan Tambahan (Opsional)
                </label>

                <textarea
                    id="context"
                    name="context"
                    placeholder="Contoh: Perjalanan santai, bawa lansia, hindari aktivitas fisik berat."
                    style="width: 100%; padding: 14px; border: 1px solid #e1e5eb; border-radius: 12px; min-height: 90px; font-family: inherit; font-size: 14px; resize: vertical;"
                >{{ old('context') }}</textarea>

            </div>


            {{-- BUTTON --}}

            <button
                type="submit"
                id="btn-submit-plan"
                class="plan-button"
            >

                ✨ Buat Rencana Perjalanan

            </button>


        </form>

    </div>

</main>

<script>
    document.addEventListener('DOMContentLoaded', function () {
        const provinceSelect = document.getElementById('province');
        const destinationSelect = document.getElementById('destination');

        // Fetch Provinces via local proxy
        fetch("{{ route('api.wilayah.provinces') }}")
            .then(response => response.json())
            .then(res => {
                if(res.data) {
                    res.data.forEach(province => {
                        let option = document.createElement('option');
                        option.value = province.code; // wilayah.id menggunakan property 'code'
                        option.text = province.name;
                        provinceSelect.add(option);
                    });
                }
            })
            .catch(error => console.error('Error fetching provinces:', error));

        // Fetch Regencies (Kota/Kabupaten) via local proxy
        provinceSelect.addEventListener('change', function () {
            const provinceId = this.value;
            destinationSelect.innerHTML = '<option value="">-- Memuat Data... --</option>';
            destinationSelect.disabled = true;

            if (provinceId) {
                fetch(`/wilayah/regencies/${provinceId}`)
                    .then(response => response.json())
                    .then(res => {
                        destinationSelect.innerHTML = '<option value="">-- Pilih Kabupaten/Kota --</option>';
                        if(res.data) {
                            res.data.forEach(regency => {
                                let option = document.createElement('option');
                                // Gunakan nama kabupaten/kota sebagai value yang akan dikirim ke backend
                                option.value = regency.name;
                                option.text = regency.name;
                                destinationSelect.add(option);
                            });
                        }
                        destinationSelect.disabled = false;
                    })
                    .catch(error => {
                        console.error('Error fetching regencies:', error);
                        destinationSelect.innerHTML = '<option value="">-- Gagal memuat data --</option>';
                    });
            } else {
                destinationSelect.innerHTML = '<option value="">-- Pilih Kabupaten/Kota --</option>';
            }
        });

        const form = document.getElementById('planner-form');
        const submitBtn = document.getElementById('btn-submit-plan');
        const errorBox = document.getElementById('client-error-box');

        function showError(msg) {
            if (errorBox) {
                errorBox.textContent = msg;
                errorBox.style.display = 'block';
                errorBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
            } else {
                alert(msg);
            }
        }

        function clearError() {
            if (errorBox) {
                errorBox.textContent = '';
                errorBox.style.display = 'none';
            }
        }

        if (form && submitBtn) {
            form.addEventListener('submit', function(e) {
                clearError();

                // 1. Validasi Provinsi
                if (!provinceSelect.value) {
                    e.preventDefault();
                    showError('Silakan pilih Provinsi terlebih dahulu.');
                    provinceSelect.focus();
                    return;
                }

                // 2. Validasi Kabupaten/Kota
                if (!destinationSelect.value || destinationSelect.disabled) {
                    e.preventDefault();
                    showError('Silakan pilih Kabupaten/Kota (Destinasi).');
                    destinationSelect.focus();
                    return;
                }

                // 3. Validasi Kategori Wisata (minimal 1 checkbox dipilih)
                const checkedPreferences = form.querySelectorAll('input[name="preferences[]"]:checked');
                if (checkedPreferences.length === 0) {
                    e.preventDefault();
                    showError('Silakan pilih minimal 1 Kategori Wisata.');
                    return;
                }

                // 4. Validasi Tanggal
                const startDate = document.getElementById('start_date').value;
                const endDate = document.getElementById('end_date').value;
                if (startDate && endDate && new Date(endDate) < new Date(startDate)) {
                    e.preventDefault();
                    showError('Tanggal selesai harus sama dengan atau setelah tanggal mulai.');
                    return;
                }

                // Jika validasi lolos, tampilkan indikator loading
                submitBtn.disabled = true;
                submitBtn.style.opacity = '0.8';
                submitBtn.innerHTML = '⌛ AI sedang menyusun rencana perjalanan... (Mohon tunggu beberapa saat)';
            });
        }
    });
</script>

</body>
</html>