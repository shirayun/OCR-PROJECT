import { Component, OnInit, OnDestroy } from '@angular/core';
import { CommonModule } from '@angular/common';
import { HttpClientModule, HttpClient, HttpEvent, HttpEventType } from '@angular/common/http';
import { RouterModule } from '@angular/router';
import { timeout } from 'rxjs/operators';

@Component({
  selector: 'app-camera',
  standalone: true,
  imports: [CommonModule, RouterModule, HttpClientModule],
  templateUrl: './camera.component.html',
  styleUrls: ['./camera.component.css']
})
export class CameraComponent implements OnInit, OnDestroy {
  videoRef!: HTMLVideoElement;
  canvasRef!: HTMLCanvasElement;
  stream: MediaStream | null = null;
  capturedBlob: Blob | null = null;
  previewUrl: string | null = null;
  result: string | null = null;
  uploading = false;
  progress = 0;
  timeoutMs = 30000; // ms

  private resizeBlob(blob: Blob, maxWidth = 1000, quality = 0.7): Promise<Blob> {
    return new Promise((resolve, reject) => {
      const img = new Image();
      const url = URL.createObjectURL(blob);
      img.onload = () => {
        let width = img.width;
        let height = img.height;
        if (width > maxWidth) {
          const scale = maxWidth / width;
          width = Math.round(width * scale);
          height = Math.round(height * scale);
        }
        const off = document.createElement('canvas');
        off.width = width;
        off.height = height;
        const ctx = off.getContext('2d')!;
        ctx.drawImage(img, 0, 0, width, height);
        off.toBlob((b) => {
          if (b) resolve(b);
          else reject(new Error('toBlob failed'));
          URL.revokeObjectURL(url);
        }, 'image/jpeg', quality);
      };
      img.onerror = (e) => {
        URL.revokeObjectURL(url);
        reject(e);
      };
      img.src = url;
    });
  }

  constructor(private http: HttpClient) {}

  ngOnInit() {
    this.startCamera();
  }

  ngOnDestroy() {
    this.stopCamera();
    if (this.previewUrl) {
      URL.revokeObjectURL(this.previewUrl);
    }
  }

  async startCamera() {
    try {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      this.videoRef = document.querySelector('video#camera') as HTMLVideoElement;
      this.videoRef.srcObject = this.stream;
      await this.videoRef.play();
    } catch (err) {
      console.error('Camera error', err);
      this.result = 'לא הצלחנו לגשת למצלמה';
    }
  }

  stopCamera() {
    if (this.stream) {
      this.stream.getTracks().forEach(t => t.stop());
      this.stream = null;
    }
  }

  capture() {
    this.canvasRef = document.querySelector('canvas#capture') as HTMLCanvasElement;
    const ctx = this.canvasRef.getContext('2d')!;
    this.canvasRef.width = this.videoRef.videoWidth || 640;
    this.canvasRef.height = this.videoRef.videoHeight || 480;
    ctx.drawImage(this.videoRef, 0, 0, this.canvasRef.width, this.canvasRef.height);
    this.canvasRef.toBlob(blob => {
      if (blob) {
        this.capturedBlob = blob;
        if (this.previewUrl) {
          URL.revokeObjectURL(this.previewUrl);
        }
        this.previewUrl = URL.createObjectURL(blob);
      }
    }, 'image/jpeg', 0.9);
  }

  upload() {
    if (!this.capturedBlob) return;
    this.uploading = true;
    this.progress = 0;
    this.result = null;

    this.resizeBlob(this.capturedBlob, 1000, 0.7).then(resized => {
      const form = new FormData();
      form.append('file', resized, 'capture.jpg');

      // ensure progress shows something quickly
      this.progress = 5;

      this.http.post('http://localhost:8000/scan', form, { reportProgress: true, observe: 'events' })
        .pipe(timeout(this.timeoutMs))
        .subscribe({
          next: (event: HttpEvent<any>) => {
            if (event.type === HttpEventType.UploadProgress) {
              const total = event.total || 1;
              this.progress = Math.round(100 * (event.loaded / total));
            } else if (event.type === HttpEventType.Response) {
              const resp = event.body;
              if (resp && resp.sr) {
                this.result = `SR: ${resp.sr} (rows: ${resp.rows})`;
              } else {
                this.result = JSON.stringify(resp, null, 2);
              }
              // ensure progress completes
              this.progress = 100;
              setTimeout(() => { this.progress = 0; }, 300);
              this.uploading = false;
            }
          },
          error: (err: any) => {
            console.error(err);
            // handle network/CORS error
            if (err?.name === 'TimeoutError') {
              this.result = 'הבקשה התנתקה — חצית את זמן ההמתנה (30s). נסי שוב או בדקי חיבור רשת.';
            } else if (err?.status === 0) {
              this.result = 'שגיאת רשת או CORS — בדקי שהשרת רץ ושה‑CORS מוגדר נכון';
            } else if (err?.error?.detail) {
              this.result = `שגיאה מהשרת: ${err.error.detail}`;
            } else {
              this.result = 'שגיאה בהעלאה';
            }
            this.uploading = false;
            this.progress = 0;
          }
        });
    }).catch(err => {
      console.error(err);
      this.result = 'שגיאה בעיבוד התמונה לפני העלאה';
      this.uploading = false;
      this.progress = 0;
    });
  }

  downloadExcel() {
    window.open('http://localhost:8000/download-results', '_blank');
  }
}
