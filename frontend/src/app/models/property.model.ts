export interface Property {
  id: string;
  title: string;
  price: number | null;
  price_per_m2: number | null;
  size_m2: number | null;
  rooms: number | null;
  bathrooms: number | null;
  floor: string | null;
  address: string | null;
  district: string | null;
  city: string | null;
  lat: number | null;
  lon: number | null;
  url: string;
  platform: string;
  images: string[];
  description: string | null;
  has_elevator: boolean | null;
  has_parking: boolean | null;
  has_terrace: boolean | null;
  is_new_development: boolean | null;
  published_at: string | null;
  scraped_at: string;
}

export interface SearchResponse {
  total: number;
  page: number;
  results: Property[];
  platforms_queried: string[];
}

export interface SearchFilters {
  city: string;
  district?: string | null;
  price_min?: number | null;
  price_max?: number | null;
  rooms_min?: number | null;
  size_min?: number | null;
  size_max?: number | null;
  platforms: string[];
  page?: number;
}

export interface PlatformAvailability {
  key: string;
  name: string;
  available: boolean;
}
