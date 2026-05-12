

import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import {
  AfterViewInit,
  Component,
  ElementRef,
  OnDestroy,
  OnInit,
  ViewChild,
} from '@angular/core';
import { FormBuilder, ReactiveFormsModule, Validators } from '@angular/forms';
import { finalize, firstValueFrom } from 'rxjs';
import {
  PlatformAvailability,
  Property,
  SearchFilters,
} from './models/property.model';
import { SearchApiService } from './services/search-api.service';

type LeafletModule = typeof import('leaflet');
type LeafletMap = import('leaflet').Map;
type LeafletMarker = import('leaflet').Marker;

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [CommonModule, ReactiveFormsModule],
  templateUrl: './app.component.html',
  styleUrl: './app.component.scss',
})
export class AppComponent implements OnInit {
  @ViewChild('mapContainer')
  private mapContainer?: ElementRef<HTMLDivElement>;

  readonly searchForm = this.fb.group({
    city: ['madrid', [Validators.required, Validators.minLength(2)]],
    district: [null as string | null],
    price_min: [null as number | null],
    price_max: [null as number | null],
    rooms_min: [null as number | null],
    size_min: [null as number | null],
    size_max: [null as number | null],
  });

  platforms: PlatformAvailability[] = [];
  selectedPlatforms = new Set<string>(['idealista']);
  properties: Property[] = [];
  platformsQueried: string[] = [];
  searchFilters: SearchFilters | null = null;

  loading = false;
  initialized = false;
  errorMessage = '';

  private leaflet?: LeafletModule;
  private map?: LeafletMap;
  private markers: LeafletMarker[] = [];
  private viewReady = false;

  constructor(
    private readonly fb: FormBuilder,
    private readonly searchApi: SearchApiService,
    private readonly http: HttpClient,
  ) {}

  /**
   * Devuelve un fragmento de hasta 5 palabras donde aparece el término de barrio/zona,
   * buscando en título, dirección, descripción y url. Resalta el término encontrado.
   */
  getDistrictSnippet(property: Property): string | null {
    const term = this.searchFilters?.district?.trim();
    if (!term) return null;
    const termLower = term.toLowerCase();
    const fields = [
      property.title || '',
      property.address || '',
      property.description || '',
      property.url || '',
    ];
    for (const field of fields) {
      const fieldLower = field.toLowerCase();
      const idx = fieldLower.indexOf(termLower);
      if (idx !== -1) {
        // Encuentra los límites de palabras alrededor del término
        const words = field.split(/\s+/);
        let wordIdx = 0, charCount = 0;
        // Encuentra en qué palabra cae el índice
        for (; wordIdx < words.length; wordIdx++) {
          if (charCount + words[wordIdx].length >= idx) break;
          charCount += words[wordIdx].length + 1;
        }
        // Toma hasta 2 palabras antes y después
        const start = Math.max(0, wordIdx - 2);
        const end = Math.min(words.length, wordIdx + 3);
        const snippetWords = words.slice(start, end);
        // Resalta el término (case-insensitive)
        const snippet = snippetWords
          .map(w => w.toLowerCase().includes(termLower) ? `<mark>${w}</mark>` : w)
          .join(' ');
        return '...' + snippet + '...';
      }
    }
    return null;
  }

  ngOnInit(): void {
    this.loadPlatforms();
    this.submitSearch();
  }

  async ngAfterViewInit(): Promise<void> {
    this.viewReady = true;
    await this.ensureMap();
    await this.renderMarkers(null);
  }

  ngOnDestroy(): void {
    this.map?.remove();
  }

  submitSearch(): void {
    if (this.searchForm.invalid) {
      this.searchForm.markAllAsTouched();
      return;
    }

    if (this.selectedPlatforms.size === 0) {
      this.errorMessage = 'Select at least one platform.';
      return;
    }

    this.loading = true;
    this.errorMessage = '';

    const city = this.searchForm.value.city ?? 'madrid';
    const filters = this.buildFilters();
    this.searchFilters = filters; // Store filters for display

    this.searchApi
      .search(filters)
      .pipe(
        finalize(() => {
          this.loading = false;
          this.initialized = true;
        }),
      )
      .subscribe({
        next: async (response) => {
          this.properties = response.results;
          this.platformsQueried = response.platforms_queried;
          // If district is provided, geocode "district, city", otherwise just "city"
          const searchLocation = filters.district ? `${filters.district}, ${city}` : city;
          const bbox = await this.geocodeCity(searchLocation);
          await this.renderMarkers(bbox);
        },
        error: async () => {
          this.properties = [];
          this.platformsQueried = [];
          const searchLocation = filters.district ? `${filters.district}, ${city}` : city;
          const bbox = await this.geocodeCity(searchLocation);
          await this.renderMarkers(bbox);
          this.errorMessage =
            'Could not load properties. Make sure backend is running on localhost:8000.';
        },
      });
  }

  togglePlatform(platformKey: string, checked: boolean): void {
    if (checked) {
      this.selectedPlatforms.add(platformKey);
      return;
    }

    this.selectedPlatforms.delete(platformKey);
  }

  trackByPropertyId(_: number, property: Property): string {
    return property.id;
  }

  asCurrency(value: number | null): string {
    if (value === null || value === undefined) {
      return 'N/A';
    }
    return new Intl.NumberFormat('es-ES', {
      style: 'currency',
      currency: 'EUR',
      maximumFractionDigits: 0,
    }).format(value);
  }

  private loadPlatforms(): void {
    this.searchApi.getPlatforms().subscribe({
      next: (platforms) => {
        this.platforms = platforms;

        if (platforms.length > 0) {
          const availableDefaults = platforms
            .filter((p) => p.available)
            .map((p) => p.key);
          if (availableDefaults.length > 0) {
            this.selectedPlatforms = new Set<string>(availableDefaults);
          }
        }
      },
      error: () => {
        this.platforms = [
          { key: 'idealista', name: 'Idealista', available: true },
          { key: 'habitaclia', name: 'Habitaclia', available: true },
          { key: 'fotocasa', name: 'Fotocasa', available: true },
          { key: 'pisos', name: 'Pisos.com', available: true },
        ];
      },
    });
  }

  private buildFilters(): SearchFilters {
    const raw = this.searchForm.getRawValue();

    return {
      city: raw.city ?? '',
      district: raw.district ?? undefined,
      price_min: raw.price_min,
      price_max: raw.price_max,
      rooms_min: raw.rooms_min,
      size_min: raw.size_min,
      size_max: raw.size_max,
      platforms: Array.from(this.selectedPlatforms),
      page: 1,
    };
  }

  private async ensureMap(): Promise<void> {
    if (!this.viewReady || !this.mapContainer || this.map) {
      return;
    }

    const leaflet = await import('leaflet');
    this.leaflet = leaflet;

    this.map = leaflet.map(this.mapContainer.nativeElement, {
      zoomControl: true,
      attributionControl: true,
    }).setView([40.4168, -3.7038], 6);

    leaflet
      .tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
      })
      .addTo(this.map);
  }

  /** Queries Nominatim for the city bounding box. Returns null on failure. */
  private async geocodeCity(

  // ...existing code...

  export class AppComponent implements OnInit {
    // ...existing code...

    /**
     * Devuelve un fragmento de hasta 5 palabras donde aparece el término de barrio/zona,
     * buscando en título, dirección, descripción y url. Resalta el término encontrado.
     */
    getDistrictSnippet(property: Property): string | null {
      const term = this.searchFilters?.district?.trim();
      if (!term) return null;
      const termLower = term.toLowerCase();
      const fields = [
        property.title || '',
        property.address || '',
        property.description || '',
        property.url || '',
      ];
      for (const field of fields) {
        const fieldLower = field.toLowerCase();
        const idx = fieldLower.indexOf(termLower);
        if (idx !== -1) {
          // Encuentra los límites de palabras alrededor del término
          const words = field.split(/\s+/);
          let wordIdx = 0, charCount = 0;
          // Encuentra en qué palabra cae el índice
          for (; wordIdx < words.length; wordIdx++) {
            if (charCount + words[wordIdx].length >= idx) break;
            charCount += words[wordIdx].length + 1;
          }
          // Toma hasta 2 palabras antes y después
          const start = Math.max(0, wordIdx - 2);
          const end = Math.min(words.length, wordIdx + 3);
          const snippetWords = words.slice(start, end);
          // Resalta el término (case-insensitive)
          const snippet = snippetWords
            .map(w => w.toLowerCase().includes(termLower) ? `<mark>${w}</mark>` : w)
            .join(' ');
          return '...' + snippet + '...';
        }
      }
      return null;
    }

  // ...existing code...
    );

    // If we have coordinates, fit to markers; otherwise fit to city bbox
    if (locatedProperties.length > 0) {
      const markerIcon = this.leaflet.icon({
        iconUrl: 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        shadowUrl:
          'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        iconRetinaUrl:
          'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        iconSize: [25, 41],
        iconAnchor: [12, 41],
        popupAnchor: [1, -30],
        shadowSize: [41, 41],
      });

      const bounds = this.leaflet.latLngBounds([]);

      for (const property of locatedProperties) {
        const marker = this.leaflet
          .marker([property.lat!, property.lon!], { icon: markerIcon })
          .bindPopup(
            `<strong>${property.title}</strong><br>` +
              `${this.asCurrency(property.price)}<br>` +
              `<a href="${property.url}" target="_blank" rel="noopener noreferrer">Ver anuncio</a>`,
          )
          .addTo(this.map);

        this.markers.push(marker);
        bounds.extend([property.lat!, property.lon!]);
      }

      this.map.fitBounds(bounds, { padding: [28, 28], maxZoom: 15 });
      return;
    }

    // No coordinates — zoom to city bounding box from Nominatim
    if (cityBbox) {
      const [s, n, w, e] = cityBbox;
      this.map.fitBounds(
        [
          [s, w],
          [n, e],
        ],
        { padding: [20, 20] },
      );
      return;
    }

    // Fallback: Spain
    this.map.setView([40.4168, -3.7038], 6);
  }
}
