import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable } from '@angular/core';
import { Observable } from 'rxjs';

import {
  PlatformAvailability,
  SearchFilters,
  SearchResponse,
} from '../models/property.model';

@Injectable({
  providedIn: 'root',
})
export class SearchApiService {
  private readonly apiBaseUrl = 'http://localhost:8000/api';

  constructor(private readonly http: HttpClient) {}

  getPlatforms(): Observable<PlatformAvailability[]> {
    return this.http.get<PlatformAvailability[]>(`${this.apiBaseUrl}/platforms`);
  }

  search(filters: SearchFilters): Observable<SearchResponse> {
    let params = new HttpParams().set('city', filters.city.trim());

    params = this.addParam(params, 'price_min', filters.price_min);
    params = this.addParam(params, 'price_max', filters.price_max);
    params = this.addParam(params, 'rooms_min', filters.rooms_min);
    params = this.addParam(params, 'size_min', filters.size_min);
    params = this.addParam(params, 'size_max', filters.size_max);
    params = this.addParam(params, 'keyword', filters.keyword);
    params = this.addParam(params, 'page', filters.page ?? 1);

    for (const platform of filters.platforms) {
      params = params.append('platforms', platform);
    }

    return this.http.get<SearchResponse>(`${this.apiBaseUrl}/search`, { params });
  }

  private addParam(
    params: HttpParams,
    key: string,
    value: string | number | null | undefined,
  ): HttpParams {
    if (value === null || value === undefined || value === '') {
      return params;
    }

    return params.set(key, String(value));
  }
}
