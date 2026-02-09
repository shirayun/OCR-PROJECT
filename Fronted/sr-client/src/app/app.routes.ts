import { Routes } from '@angular/router';

export const routes: Routes = [
  { path: '', loadComponent: () => import('./camera.component').then(m => m.CameraComponent) }
];
