import { of } from 'rxjs';
import { TestBed } from '@angular/core/testing';

import { AppComponent } from './app.component';
import { SearchApiService } from './services/search-api.service';

describe('AppComponent', () => {
  const searchApiMock = {
    getPlatforms: jasmine.createSpy('getPlatforms').and.returnValue(
      of([{ key: 'idealista', name: 'Idealista', available: true }]),
    ),
    search: jasmine.createSpy('search').and.returnValue(
      of({ total: 0, page: 1, results: [], platforms_queried: ['idealista'] }),
    ),
  };

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [AppComponent],
      providers: [{ provide: SearchApiService, useValue: searchApiMock }],
    }).compileComponents();
  });

  it('should create the app', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app).toBeTruthy();
  });

  it('should initialize with one selected platform', () => {
    const fixture = TestBed.createComponent(AppComponent);
    const app = fixture.componentInstance;
    expect(app.selectedPlatforms.has('idealista')).toBeTrue();
  });

  it('should render hero title', () => {
    const fixture = TestBed.createComponent(AppComponent);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('h1')?.textContent).toContain('Buscador de vivienda');
  });
});
