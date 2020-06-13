set -e
echo Deploying..
cp -R . /tmp/client
cd /tmp/client
git init
git add -A
git commit -m 'auto deploy'

git push -f $1 master
rm -rf /tmp/client