<?php

use Illuminate\Support\Facades\Route;
use App\Http\Controllers\TravelPlannerController;

Route::get('/', [TravelPlannerController::class, 'index'])
    ->name('travel.index');

Route::post('/travel/plan', [TravelPlannerController::class, 'plan'])
    ->name('travel.plan');

Route::get('/wilayah/provinces', [TravelPlannerController::class, 'provinces'])
    ->name('api.wilayah.provinces');

Route::get('/wilayah/regencies/{code}', [TravelPlannerController::class, 'regencies'])
    ->name('api.wilayah.regencies');

Route::post('/travel/regenerate-item', [TravelPlannerController::class, 'regenerateItem'])
    ->name('travel.regenerate_item');

Route::post('/trips/save', [TravelPlannerController::class, 'save'])
    ->name('travel.save');

Route::get('/trips', [TravelPlannerController::class, 'history'])
    ->name('travel.history');

Route::get('/trips/{id}', [TravelPlannerController::class, 'show'])
    ->name('travel.show');

Route::get('/trips/{id}/pdf', [TravelPlannerController::class, 'pdf'])
    ->name('travel.pdf');

Route::delete('/trips/{id}', [TravelPlannerController::class, 'destroy'])
    ->name('travel.destroy');