import React, { useRef, useEffect } from 'react';

const SimpleVideoTest = () => {
  const videoRef = useRef(null);

  useEffect(() => {
    const video = videoRef.current;
    if (video) {
      video.addEventListener('error', (e) => {
        console.error('Video error:', e);
      });
    }
  }, []);

  const handleVideoError = (e) => {
    console.error('Video error event:', e);
    console.log('Video URL:', e.target.src);
  };

  return (
    <div>
      <h1>Simple React Video Test</h1>
      <video 
        ref={videoRef}
        width="640" 
        height="480" 
        controls
        src="http://localhost:5004/final/project_18_assembler.mp4"
        onError={handleVideoError}
      >
        Your browser does not support the video tag.
      </video>
    </div>
  );
};

export default SimpleVideoTest;