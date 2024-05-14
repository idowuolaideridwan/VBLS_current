function playVideo(commentTime) {
    var videoPlayer = videojs("video-player");
    videoPlayer.src({ type: "video/mp4", src: "{{ url_for('static', filename='video.mp4') }}#t=" + commentTime });
    videoPlayer.play();
}
