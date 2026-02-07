import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'camera' },
  { path: 'camera', loadComponent: () => import('./camera.component').then(m => m.CameraComponent) }
];
