<?php

namespace App\Http\Controllers;

use Illuminate\Http\Request;
use Illuminate\Support\Facades\Http;
use App\Services\OpenStreetMapService;
use App\Models\Trip;


class TravelPlannerController extends Controller
{
    public function index()
    {
        return view('travel.index');
    }

    public function provinces()
    {
        try {
            $response = Http::withoutVerifying()->timeout(15)->get('https://wilayah.id/api/provinces.json');
            return response()->json($response->json() ?? ['data' => []]);
        } catch (\Exception $e) {
            return response()->json(['data' => []], 500);
        }
    }

    public function regencies($code)
    {
        try {
            $response = Http::withoutVerifying()->timeout(15)->get("https://wilayah.id/api/regencies/{$code}.json");
            return response()->json($response->json() ?? ['data' => []]);
        } catch (\Exception $e) {
            return response()->json(['data' => []], 500);
        }
    }



    public function plan(
        Request $request,
        OpenStreetMapService $osm
    ) {
        set_time_limit(0);

        /*
        |--------------------------------------------------------------------------
        | VALIDASI INPUT
        |--------------------------------------------------------------------------
        */

        $validated = $request->validate([

            'destination' => 'required|string|max:100',

            'start_date' => 'required|date',

            'end_date' => [
                'required',
                'date',
                'after_or_equal:start_date'
            ],

            'jumlah_orang' => [
                'required',
                'integer',
                'min:1'
            ],

            'budget' => [
                'required',
                'numeric',
                'min:0'
            ],

            'preferences' => [
                'required',
                'array',
                'min:1'
            ],

            'preferences.*' => [
                'string',
                'in:pantai,kuliner,alam,budaya,hiburan'
            ],

            'context' => 'nullable|string|max:1000',

        ]);


        /*
        |--------------------------------------------------------------------------
        | CARI DESTINASI DENGAN OPENSTREETMAP
        |--------------------------------------------------------------------------
        */

        $destination = $osm->searchDestination(
            $validated['destination']
        );


        /*
        |--------------------------------------------------------------------------
        | FALLBACK JIKA OSM TIDAK MENEMUKAN DESTINASI
        |--------------------------------------------------------------------------
        */

        if (!$destination) {

            $destination = [

                'display_name' => $validated['destination'],

                'lat' => null,

                'lon' => null,

            ];
        }


        /*
        |--------------------------------------------------------------------------
        | KIRIM DATA KE PYTHON AI
        |--------------------------------------------------------------------------
        */

        try {

            $pythonUrl = rtrim(env('PYTHON_AI_URL', 'http://127.0.0.1:8002'), '/');

            $response = Http::timeout(600)
                ->post(
                    $pythonUrl . '/plan',
                    [

                        'destination' =>
                            $validated['destination'],

                        'start_date' =>
                            $validated['start_date'],

                        'end_date' =>
                            $validated['end_date'],

                        'jumlah_orang' =>
                            (int) $validated['jumlah_orang'],

                        'budget' =>
                            (float) $validated['budget'],

                        'preferences' =>
                            $validated['preferences'],

                        'context' =>
                            $validated['context'] ?? '',

                    ]
                );


            /*
            |--------------------------------------------------------------------------
            | CEK RESPONSE PYTHON
            |--------------------------------------------------------------------------
            */

            if (!$response->successful()) {

                return back()
                    ->withInput()
                    ->with(
                        'error',
                        'Python AI Travel Planner memberikan error. Status: '
                        . $response->status()
                    );
            }


            /*
            |--------------------------------------------------------------------------
            | AMBIL HASIL AI
            |--------------------------------------------------------------------------
            */

            $aiResult = $response->json();


            /*
            |--------------------------------------------------------------------------
            | CEK APAKAH RESPONSE BERUPA ARRAY
            |--------------------------------------------------------------------------
            */

            if (!is_array($aiResult)) {

                return back()
                    ->withInput()
                    ->with(
                        'error',
                        'Response dari Python AI tidak valid.'
                    );
            }


            /*
            |--------------------------------------------------------------------------
            | CEK ERROR DARI PYTHON
            |--------------------------------------------------------------------------
            */

            if (
                isset($aiResult['status']) &&
                $aiResult['status'] === 'error'
            ) {

                return back()
                    ->withInput()
                    ->with(
                        'error',
                        $aiResult['message']
                            ?? 'AI gagal membuat rencana perjalanan.'
                    );
            }


            /*
            |--------------------------------------------------------------------------
            | PASTIKAN ITINERARY ADA
            |--------------------------------------------------------------------------
            */

            if (
                !isset($aiResult['itinerary']) ||
                !is_array($aiResult['itinerary'])
            ) {

                return back()
                    ->withInput()
                    ->with(
                        'error',
                        'AI tidak mengembalikan rekomendasi perjalanan.'
                    );
            }


            /*
            |--------------------------------------------------------------------------
            | TAMPILKAN HALAMAN HASIL
            |--------------------------------------------------------------------------
            */

            return view(
                'travel.result',
                [

                    'trip' => $validated,

                    'destination' => $destination,

                    'aiResult' => $aiResult,

                ]
            );

        }

        catch (\Exception $e) {

            return back()
                ->withInput()
                ->with(
                    'error',
                    'Tidak dapat terhubung ke Python AI: ' . $e->getMessage()
                    . '. Pastikan main.py sedang berjalan pada port 8002.'
                );
        }
    }

    public function regenerateItem(Request $request)
    {
        $validated = $request->validate([
            'destination' => 'required|string',
            'category' => 'required|string',
            'current_place' => 'required|string',
            'context' => 'nullable|string',
            'trip_id' => 'nullable|integer',
            'day_index' => 'nullable|integer',
            'activity_index' => 'nullable|integer',
        ]);

        try {
            $pythonUrl = rtrim(env('PYTHON_AI_URL', 'http://127.0.0.1:8002'), '/');
            $response = Http::timeout(120)->post($pythonUrl . '/regenerate', [
                'destination' => $validated['destination'],
                'category' => $validated['category'],
                'current_place' => $validated['current_place'],
                'context' => $validated['context'] ?? '',
            ]);

            if ($response->successful()) {
                $result = $response->json();
                
                // Jika trip sudah disimpan ke DB, update itinerary di DB
                if (!empty($validated['trip_id']) && isset($validated['day_index']) && isset($validated['activity_index'])) {
                    $trip = Trip::find($validated['trip_id']);
                    if ($trip && ($result['status'] ?? '') === 'success') {
                        $itinerary = $trip->itinerary;
                        $d = (int) $validated['day_index'];
                        $a = (int) $validated['activity_index'];
                        if (isset($itinerary[$d]['activities'][$a])) {
                            $itinerary[$d]['activities'][$a]['nama_tempat'] = $result['nama_tempat'];
                            $itinerary[$d]['activities'][$a]['deskripsi'] = $result['deskripsi'];
                            $itinerary[$d]['activities'][$a]['estimasi_biaya'] = $result['estimasi_biaya'];
                            $itinerary[$d]['activities'][$a]['lat'] = $result['lat'];
                            $itinerary[$d]['activities'][$a]['lon'] = $result['lon'];
                            $itinerary[$d]['activities'][$a]['is_available'] = $result['is_available'] ?? true;
                            $trip->itinerary = $itinerary;
                            $trip->save();
                        }
                    }
                }

                return response()->json($result);
            }

            return response()->json([
                'status' => 'error',
                'message' => 'Gagal mengambil tempat alternatif dari Python AI.'
            ], 500);

        } catch (\Exception $e) {
            return response()->json([
                'status' => 'error',
                'message' => 'Tidak dapat terhubung ke Python AI: ' . $e->getMessage()
            ], 500);
        }
    }

    public function save(Request $request)
    {
        $validated = $request->validate([
            'destination' => 'required|string|max:150',
            'start_date' => 'required|date',
            'end_date' => 'required|date',
            'jumlah_orang' => 'required|integer|min:1',
            'budget' => 'required|numeric|min:0',
            'preferences' => 'nullable|array',
            'context' => 'nullable|string',
            'summary' => 'nullable|string',
            'budget_breakdown' => 'nullable|array',
            'itinerary' => 'required|array',
        ]);

        try {
            $trip = Trip::create([
                'destination' => $validated['destination'],
                'start_date' => $validated['start_date'],
                'end_date' => $validated['end_date'],
                'jumlah_orang' => $validated['jumlah_orang'],
                'budget' => $validated['budget'],
                'preferences' => $validated['preferences'] ?? [],
                'context' => $validated['context'] ?? '',
                'summary' => $validated['summary'] ?? '',
                'budget_breakdown' => $validated['budget_breakdown'] ?? [],
                'itinerary' => $validated['itinerary'],
            ]);

            return response()->json([
                'status' => 'success',
                'message' => 'Rencana perjalanan berhasil disimpan!',
                'trip_id' => $trip->id
            ]);
        } catch (\Exception $e) {
            return response()->json([
                'status' => 'error',
                'message' => 'Gagal menyimpan rencana perjalanan: ' . $e->getMessage()
            ], 500);
        }
    }

    public function history()
    {
        $trips = Trip::orderBy('created_at', 'desc')->get();
        return view('travel.history', compact('trips'));
    }

    public function show($id)
    {
        $trip = Trip::findOrFail($id);

        $destination = [
            'display_name' => $trip->destination,
            'lat' => null,
            'lon' => null,
        ];

        if (!empty($trip->itinerary)) {
            foreach ($trip->itinerary as $day) {
                foreach ($day['activities'] ?? [] as $act) {
                    if (!empty($act['lat']) && !empty($act['lon'])) {
                        $destination['lat'] = $act['lat'];
                        $destination['lon'] = $act['lon'];
                        break 2;
                    }
                }
            }
        }

        $aiResult = [
            'summary' => $trip->summary,
            'budget_breakdown' => $trip->budget_breakdown,
            'itinerary' => $trip->itinerary,
        ];

        $tripInput = [
            'destination' => $trip->destination,
            'start_date' => $trip->start_date ? $trip->start_date->format('Y-m-d') : '',
            'end_date' => $trip->end_date ? $trip->end_date->format('Y-m-d') : '',
            'jumlah_orang' => $trip->jumlah_orang,
            'budget' => $trip->budget,
            'preferences' => $trip->preferences ?? [],
            'context' => $trip->context ?? '',
        ];

        return view('travel.result', [
            'trip' => $tripInput,
            'destination' => $destination,
            'aiResult' => $aiResult,
            'savedTripId' => $trip->id
        ]);
    }

    public function destroy($id)
    {
        $trip = Trip::findOrFail($id);
        $trip->delete();

        return redirect()->route('travel.history')->with('success', 'Rencana perjalanan telah dihapus.');
    }

    public function pdf($id)
    {
        $trip = Trip::findOrFail($id);
        return view('travel.pdf', compact('trip'));
    }
}